"""Research a program's requirement rules from the university's public pages.

This is step one of the two-step design: **the AI decides, and the decision is
cached as data.** This module is the deciding half. ``app/services/requirement_rules.py``
is the reading half, and after the first student in a program it is the only half
that runs.

Nothing here writes a course. The output is a set of *rules* — which subject
families, at which levels, minus which exclusions, satisfy a named bucket — plus
the URLs those rules were read from. A rule can never introduce a course code
into the catalog; it can only classify a course the catalog already knows about.
That boundary is what keeps a research failure from becoming a fabricated course.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.research_client import (
    ResearchDisabledError,
    UngroundedResearchError,
    extract_json,
    is_research_enabled,
    research,
)
from app.config import settings
from app.models.requirement_rule import BASIS_INFERRED, RequirementRule
from app.research.schema import (
    RuleRejected,
    _root_domain,
    normalize_rules,
    validate_sources,
)

logger = logging.getLogger("acadvo.research.program_rules")


class ResearchFailed(RuntimeError):
    """Research ran but produced nothing storable. Carries a readable reason."""


# ── Provenance: whose pages a program's rules are allowed to come from ──
#
# `RequirementRule` rows are keyed on (university, program) *globally* — that is
# the whole point of the design: one student researches a program and everyone
# in it is covered. Both of those strings are free text on the requesting
# student's own profile, so without a provenance check the sharing is also the
# attack: register, set `university = "York University"` and
# `program = "Computer Science"`, POST a page written to read like a calendar,
# and `store_rules` replaces the real cohort's rules with the attacker's — after
# which every York CS student is told which courses "count" by a stranger's web
# page, with a source_quote to make it look authoritative.
#
# Shape validation cannot catch this. `normalize_rule` asks whether a rule is
# well formed, never whose page it came from; an attacker's page can be
# perfectly well formed. So the check has to be on the *origin* of the pages,
# which is the one thing the attacker cannot forge: the registrable domain of
# the URL this server actually fetched.
#
# The rule, in two halves:
#
#   (a) Known university — its pages must be on its own registrable domain.
#       `UNIVERSITY_DOMAINS` in ai/tool_executor.py is the existing map and is
#       imported rather than copied, so adding a school stays a one-line change
#       in one place.
#
#   (b) Unknown university — this is a real product path, not an edge case: the
#       map holds 26 Canadian schools and the app is meant to grow past them, so
#       refusing research outright would mean nobody at school 27 can ever be
#       covered. Refusing is safer only if you ignore that. Instead an unknown
#       university gets *first-writer-pins-the-domain*: the first successful run
#       may write, and from then on `_check_domain_conflict` refuses any run
#       whose pages are on a different registrable domain, so a second party
#       cannot take the program over. Those rules are additionally stored with
#       `basis = inferred` no matter what the model claimed, because "the
#       university's page states this" is exactly the assertion we could not
#       verify — and the UI renders `stated` as fact ("named in the
#       requirement") while it hedges `inferred`.
#
# Half (b) — the domain conflict — applies to known universities too. It is what
# stops one cohort's verified rules from being *deleted* as a side effect of
# someone else's run.


def _normalize_university(name: str | None) -> str:
    """Fold a university name for map lookup.

    Case-and-space folded on purpose. The lookup decides whether the domain gate
    applies at all, so an exact-match lookup would hand an attacker the bypass:
    `university = "york university"` misses the map, reads as an unknown school,
    and skips the yorku.ca requirement entirely.
    """
    return " ".join((name or "").split()).casefold()


def expected_domain(university: str | None) -> str | None:
    """The registrable domain this university's own pages live on, or None.

    None means "not in the map" — an unknown school, handled by the
    first-writer-pins policy above, never as an implicit pass.
    """
    # Imported inside the function to keep this module free of the AI tool
    # layer's import graph (ai/tool_executor pulls in half the model layer);
    # ``services/semester_plan.py`` reads the same map the same way.
    from app.ai.tool_executor import UNIVERSITY_DOMAINS

    wanted = _normalize_university(university)
    if not wanted:
        return None
    for name, domain in UNIVERSITY_DOMAINS.items():
        if _normalize_university(name) == wanted:
            return domain
    return None


def check_requirements_url(university: str | None, url: str) -> str:
    """Reject a requirements-page URL that is not on the university's own domain.

    The first line of defence for the cross-tenant poisoning above, and the one
    that can explain itself to the student who typed the wrong link. It is
    deliberately not the *only* line: ``store_rules`` re-checks the pages that
    were actually fetched, because a redirect, an already-queued job or a future
    caller could all put URLs into a job without passing through here.

    Raises ``RuleRejected`` (which the router renders as a 422) with a message
    naming the domain that would be accepted.
    """
    domain = expected_domain(university)
    if domain is None:
        # Unknown school: nothing to compare against. `validate_requirements_url`
        # has already rejected non-public and denylisted hosts, and the
        # first-writer-pins rule in `store_rules` bounds what this can do.
        return url
    if _root_domain(url) != domain:
        raise RuleRejected(
            f"that page is not on {university}'s own website — link a page on "
            f"{domain} (its academic calendar or program-requirements page)"
        )
    return url


def source_domains(sources: list[dict] | None) -> set[str]:
    """The registrable domains of a set of citations, ignoring empty entries."""
    out = set()
    for s in sources or []:
        if not isinstance(s, dict):
            continue
        root = _root_domain(s.get("domain") or s.get("uri") or "")
        if root:
            out.add(root)
    return out


def _check_source_provenance(university: str, sources: list[dict]) -> bool:
    """Enforce half (a). Returns whether the provenance could be *verified*.

    Raises ``ResearchFailed`` when the university is known and none of the pages
    that were actually read belong to it — the case where a well-formed answer
    was extracted from somebody else's website.
    """
    domain = expected_domain(university)
    domains = source_domains(sources)
    if domain is None:
        return False
    if domain not in domains:
        raise ResearchFailed(
            f"the pages that were read ({', '.join(sorted(domains)) or 'none'}) "
            f"are not on {university}'s own domain ({domain}), so these rules "
            "will not be stored for that program"
        )
    return True


async def _check_domain_conflict(
    db: AsyncSession, university: str, program: str, incoming: set[str]
) -> None:
    """Enforce half (b): a run may not destroy rules from a different origin.

    ``store_rules`` deletes every bucket the new run did not produce, so an
    accepted run is a full replacement of the program's rules. That is correct
    when the same source is being re-read and catastrophic when it is not: one
    request would wipe a cohort's verified requirements. So a run whose pages
    share no registrable domain with the stored rules' pages is refused outright
    — nothing written, nothing deleted — and a human has to reconcile it.

    Existing rows carrying no recorded domain are the pre-provenance shape and
    are not treated as a claim on the program; refusing on their behalf would
    freeze those programs permanently with no way to re-research them.
    """
    result = await db.execute(
        select(RequirementRule.source_urls).where(
            RequirementRule.university == university,
            RequirementRule.program == program,
        )
    )
    existing: set[str] = set()
    for urls in result.scalars():
        existing |= source_domains(urls)
    if existing and incoming and not (existing & incoming):
        raise ResearchFailed(
            f"this program's stored rules were read from "
            f"{', '.join(sorted(existing))}; a run from "
            f"{', '.join(sorted(incoming))} will not be allowed to replace them"
        )


SYSTEM_INSTRUCTION = """You are a careful academic-calendar analyst. You read a \
university's own published pages and report what they say about degree \
requirements.

Three rules govern everything you output:

1. Only report what you actually read on a page you retrieved. If you cannot \
find a requirement on an official page, omit that bucket entirely. An omitted \
bucket is a correct answer; a guessed one is not.
2. Distinguish reading from concluding. Set "basis" to "stated" ONLY when a \
single sentence on the page says the rule, and quote that sentence in \
"source_quote". If you worked the rule out by combining several parts of a page, \
set "basis" to "inferred".
3. An exclusion list is not an option list. Pages say both "the following \
satisfy this requirement" and "the following will NOT count towards this \
requirement", often one after the other. Courses from the second kind of \
sentence go in "excluded_codes" and NEVER in "stated_codes".

Prefer the university's own domain: its academic calendar, its faculty's degree \
requirements pages, its program checklists. Never rely on student forums, \
note-sharing sites, or aggregators."""


def build_prompt(university: str, program: str, *, urls: list[str] | None = None) -> str:
    where = (
        "on the page(s) given below"
        if urls
        else "on that university's own official website"
    )
    return f"""Find the current degree requirements for the **{program}** program at \
**{university}**, {where}.

Report each requirement bucket (major/core requirements, mathematics, general \
education / breadth / distribution, science, electives, and any others the \
program defines) as a MATCHABLE RULE rather than as a list of courses. Most \
buckets are defined as rules — "6.00 credits in AP/HUMA" — and hundreds of \
courses satisfy them, so an enumerated list would be wrong and incomplete.

Return ONLY a JSON object, no prose and no markdown fences:

{{
  "university": "the university's own name for itself",
  "program": "the program's official name",
  "calendar_year": "e.g. 2025-2026, or null if the page does not say",
  "rules": [
    {{
      "bucket_name": "the requirement's name as the page writes it",
      "credits_required": 6.0,
      "allowed_subjects": ["AP/HUMA", "AP/SOSC"],
      "level_floor": 1000,
      "level_ceiling": null,
      "stated_codes": ["SC/BIOL 1000"],
      "excluded_codes": ["SC/BIOL 1500"],
      "excluded_subjects": ["EECS"],
      "source_quote": "the exact sentence the rule was read from",
      "basis": "stated",
      "notes": "any condition that does not fit the fields above"
    }}
  ]
}}

Field meanings — follow these exactly:
- "allowed_subjects": subject prefixes as the university writes them \
("AP/HUMA", "CMPT"). Never a wildcard, never a full course code.
- "level_floor"/"level_ceiling": course-number bounds, e.g. 2000 for \
"2000-level or above". Use null when the page states no bound.
- "stated_codes": ONLY specific courses the page names as satisfying this \
bucket.
- "excluded_codes"/"excluded_subjects": ONLY things the page says do NOT count.
- "basis": "stated" if one sentence says the whole rule (quote it), otherwise \
"inferred".

Omit any bucket you could not find on an official page. If you found nothing at \
all, return {{"rules": []}}."""


async def research_program_rules(
    university: str, program: str, urls: list[str] | None = None
) -> dict:
    """Run the research call and return validated, storable rules.

    ``urls`` are the university pages to read — normally the one a student
    supplied for their program. Without them the pages have to be found by
    searching, which is off by default because a search blows the free tier's
    per-request token ceiling; see ``settings.RESEARCH_USE_SEARCH_GROUNDING``.

    Returns ``{"rules": [ExtractedRule], "sources": [...], "rejected": [...],
    "model": str}``. Raises ``ResearchDisabledError`` when unconfigured and
    ``ResearchFailed`` for every other unusable outcome, with the reason in the
    message so the job row records something a human can act on.
    """
    if not is_research_enabled():
        raise ResearchDisabledError()

    if not urls and not settings.RESEARCH_USE_SEARCH_GROUNDING:
        raise ResearchFailed(
            "no requirements page was given for this program, and searching for "
            "one is disabled (a web search does not fit the free tier's "
            "per-request token limit). Supply the URL of the program's official "
            "requirements page."
        )

    try:
        result = await research(
            build_prompt(university, program, urls=urls),
            urls=urls,
            system_instruction=SYSTEM_INSTRUCTION,
        )
    except UngroundedResearchError as exc:
        # Not retried as a transient error: an ungrounded answer means the model
        # chose to answer from memory, and asking again invites the same thing
        # with different wording.
        raise ResearchFailed(str(exc)) from exc

    payload = extract_json(result.text)
    if payload is None:
        raise ResearchFailed("research output was not JSON")
    if isinstance(payload, list):
        payload = {"rules": payload}
    if not isinstance(payload, dict):
        raise ResearchFailed("research output was not an object")

    try:
        sources = validate_sources([s.as_dict() for s in result.sources])
    except RuleRejected as exc:
        raise ResearchFailed(str(exc)) from exc

    rules, rejected = normalize_rules(payload.get("rules"))
    if rejected:
        logger.warning(
            "research: rejected %d rule(s) for %s / %s: %s",
            len(rejected),
            university,
            program,
            "; ".join(rejected[:5]),
        )
    if not rules:
        raise ResearchFailed(
            "no rule survived validation"
            + (f" ({rejected[0]})" if rejected else " (the model reported none)")
        )

    return {
        "rules": rules,
        "sources": sources,
        "rejected": rejected,
        "model": result.model,
        "calendar_year": payload.get("calendar_year"),
    }


async def store_rules(
    db: AsyncSession,
    university: str,
    program: str,
    rules: list,
    sources: list[dict],
    model: str,
) -> int:
    """Upsert researched rules for ``(university, program)``.

    Replaces the stored rule for a bucket rather than accumulating versions: a
    re-run after a calendar update should leave the *current* rule in place, and
    the previous one is not something advising should ever fall back to. Buckets
    that vanish from a later run are deleted for the same reason — a rule the
    university no longer publishes must stop being applied.

    Written with plain selects rather than a dialect-specific upsert so the same
    path runs under Postgres and the SQLite test harness.

    Provenance is checked *here*, before anything is written or deleted, because
    this is the single choke point every rule write passes through — see the
    provenance section at the top of this module for the attack it stops. Both
    checks raise ``ResearchFailed``, which the runner records on the job, so a
    refused run reads as a failed research attempt rather than as silence.
    """
    incoming_domains = source_domains(sources)
    verified = _check_source_provenance(university, sources)
    await _check_domain_conflict(db, university, program, incoming_domains)

    now = datetime.now(timezone.utc)
    existing_result = await db.execute(
        select(RequirementRule).where(
            RequirementRule.university == university,
            RequirementRule.program == program,
        )
    )
    existing = {r.bucket_name.strip().lower(): r for r in existing_result.scalars()}

    written = 0
    kept: set[str] = set()
    for rule in rules:
        key = rule.bucket_name.strip().lower()
        kept.add(key)
        row = existing.get(key)
        if row is None:
            row = RequirementRule(
                university=university, program=program, bucket_name=rule.bucket_name
            )
            db.add(row)
        row.bucket_name = rule.bucket_name
        row.credits_required = rule.credits_required
        row.allowed_subjects = list(rule.allowed_subjects)
        row.level_floor = rule.level_floor
        row.level_ceiling = rule.level_ceiling
        row.stated_codes = list(rule.stated_codes)
        row.excluded_codes = list(rule.excluded_codes)
        row.excluded_subjects = list(rule.excluded_subjects)
        row.source_quote = rule.source_quote
        row.notes = rule.notes
        # A rule from a domain we could not tie to the university keeps whatever
        # it says, but never the *claim* that the university stated it: `stated`
        # renders as fact in the UI ("named in the requirement"), and an
        # unverifiable page saying so is precisely what must not be repeated as
        # one. Downgrade only — the same "default down, never up" rule
        # `normalize_rule` applies to a missing source_quote.
        row.basis = rule.basis if verified else BASIS_INFERRED
        row.source_urls = list(sources)
        row.extracted_at = now
        row.extracted_by = (model or "")[:64]
        row.updated_at = now
        written += 1

    for key, row in existing.items():
        if key not in kept:
            await db.delete(row)

    await db.commit()
    logger.info(
        "research: stored %d rule(s) for %s / %s from %d source(s)",
        written,
        university,
        program,
        len(sources),
    )
    return written


async def run_research(
    db: AsyncSession, university: str, program: str, urls: list[str] | None = None
) -> int:
    """Research and store in one step. Returns the number of rules written."""
    outcome = await research_program_rules(university, program, urls)
    return await store_rules(
        db,
        university,
        program,
        outcome["rules"],
        outcome["sources"],
        outcome["model"],
    )


def rule_ttl() -> timedelta:
    return timedelta(days=max(1, settings.REQUIREMENT_RULE_TTL_DAYS))


def is_stale(extracted_at: datetime | None, *, now: datetime | None = None) -> bool:
    """True when a rule is older than the TTL and should be re-checked.

    Stale rules are still served — a rule from last year's calendar is far more
    useful than silence, and most requirements do not change — but they are
    flagged to the student and queued for refresh.
    """
    if extracted_at is None:
        return True
    now = now or datetime.now(timezone.utc)
    if extracted_at.tzinfo is None:
        # SQLite hands back naive datetimes; treat them as UTC rather than
        # crashing the comparison inside a request.
        extracted_at = extracted_at.replace(tzinfo=timezone.utc)
    return (now - extracted_at) > rule_ttl()
