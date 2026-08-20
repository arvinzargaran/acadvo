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
from app.models.requirement_rule import RequirementRule
from app.research.schema import RuleRejected, normalize_rules, validate_sources

logger = logging.getLogger("acadvo.research.program_rules")


class ResearchFailed(RuntimeError):
    """Research ran but produced nothing storable. Carries a readable reason."""


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
    supplied for their program. Without them the model has to find the pages
    itself, which requires Search grounding (billed); see
    ``settings.RESEARCH_USE_SEARCH_GROUNDING``.

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
            "one is disabled (Google Search grounding is a paid feature). Supply "
            "the URL of the program's official requirements page."
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
    """
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
        row.basis = rule.basis
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
