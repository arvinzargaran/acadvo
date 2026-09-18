"""Server-side eligibility / validation for AI-generated course picks.

The AI is grounded in the real catalog (see ``catalog.get_catalog``), but we never
trust the model's output blindly. These helpers let the recommendation and
semester-plan services:

  (a) confirm a returned code actually exists in the catalog (drop fabrications),
  (b) look up the authoritative name/credits to overwrite the LLM's text, and
  (c) decide whether a student is ELIGIBLE for a course given their completed
      courses (prerequisites) and their major GPA (GPA gates),
  (d) decide whether a course SATISFIES a requirement bucket, using the program's
      cached requirement rules (see ``satisfies_bucket`` below).

(a)-(c) answer "can I take this?". (d) answers the different and more dangerous
question "does this count?" — dangerous because a wrong answer is invisible until
a graduation audit, which is why its verdicts carry a stated/inferred label and
the URLs they were read from rather than being reduced to a boolean.

Prerequisite model (matches ``catalog``): ``prerequisites`` is a list of requirement
GROUPS. It is satisfied when, for EVERY group, at least ONE code in that group is in
the student's satisfied set (AND across groups, OR within a group). ``[]`` = none.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.program_config import get_graduate_rule
from app.data.york_cs_catalog import EQUIVALENT_GROUPS
from app.models.degree import Course, CourseStatus
from app.services.degree import calculate_major_gpa
from app.config import settings
from app.services.document_parser import normalize_course_code


def equivalents_of(code: str) -> set[str]:
    """Return ``code`` plus any courses it is mutually equivalent to (e.g. the
    first-year intro alternatives). Completing any member satisfies them all."""
    norm = normalize_course_code(code)
    out = {norm}
    for group in EQUIVALENT_GROUPS:
        if norm in group:
            out |= set(group)
    return out


def expand_equivalents(codes: set[str]) -> set[str]:
    """Expand a set of codes with all their equivalents."""
    out: set[str] = set()
    for c in codes:
        out |= equivalents_of(c)
    return out


async def get_completed_codes(user_id: uuid.UUID, db: AsyncSession) -> set[str]:
    """Return the set of canonical codes the student has COMPLETED."""
    result = await db.execute(
        select(Course).where(
            Course.user_id == user_id,
            Course.status == CourseStatus.completed,
        )
    )
    completed = {
        normalize_course_code(c.course_code)
        for c in result.scalars()
        if c.course_code
    }
    # A completed course also satisfies any course it's equivalent to.
    return expand_equivalents(completed)


def missing_prerequisite_group(
    prerequisites: list[list[str]] | None,
    satisfied_codes: set[str],
) -> list[str] | None:
    """Return the FIRST requirement group that is not satisfied, or ``None`` if all
    groups are satisfied. ``satisfied_codes`` are canonical codes the student has
    completed (and, for plan-aware checks, scheduled earlier)."""
    for group in prerequisites or []:
        if not any(normalize_course_code(c) in satisfied_codes for c in group):
            return [normalize_course_code(c) for c in group]
    return None


def _fmt_gpa(value: float | None) -> str:
    return "N/A" if value is None else f"{round(value, 2)}"


def gate_blocked_reason(
    gpa_gate: dict | None,
    gpa_value: float | None,
    *,
    plan_phrasing: bool = False,
) -> str | None:
    """Return a human-readable reason string if ``gpa_value`` fails the gate, else
    ``None``. ``plan_phrasing`` softens the wording for a forward-looking plan
    ("unlocks once ...")."""
    if not gpa_gate:
        return None
    minimum = float(gpa_gate.get("min", 4.50))
    if gpa_value is not None and gpa_value >= minimum:
        return None
    scope = gpa_gate.get("scope", "")
    if plan_phrasing:
        return f"Unlocks once {scope} GPA ≥ {minimum:.2f} (currently {_fmt_gpa(gpa_value)})"
    return f"Requires {scope} GPA ≥ {minimum:.2f} (yours: {_fmt_gpa(gpa_value)})"


def evaluate_entry(
    entry: dict,
    satisfied_codes: set[str],
    gpa_by_scope: dict[str, float | None],
    *,
    plan_phrasing: bool = False,
) -> str | None:
    """Given a catalog ENTRY, the student's satisfied codes and a scope->gpa map,
    return a ``blocked_reason`` string if the student is INELIGIBLE, else ``None``.

    Prerequisites are checked first, then the GPA gate."""
    missing = missing_prerequisite_group(entry.get("prerequisites"), satisfied_codes)
    if missing:
        return f"Missing prerequisite {' or '.join(missing)}"
    gate = entry.get("gpa_gate")
    if gate:
        scope = gate.get("scope", "")
        gpa_value = gpa_by_scope.get(scope)
        reason = gate_blocked_reason(gate, gpa_value, plan_phrasing=plan_phrasing)
        if reason:
            return reason
    return None


async def gpa_by_scope_for_catalog(
    catalog: dict[str, dict],
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, float | None]:
    """Compute the student's major GPA for every distinct GPA-gate scope that
    appears in the catalog, returning ``{scope: gpa_value_or_None}``."""
    scopes = {
        e["gpa_gate"]["scope"]
        for e in catalog.values()
        if e.get("gpa_gate") and e["gpa_gate"].get("scope")
    }
    out: dict[str, float | None] = {}
    for scope in scopes:
        result = await calculate_major_gpa(user_id, db, faculty_prefix=scope)
        out[scope] = result["gpa"]
    return out


# ── Bucket satisfaction (the "does this count?" question) ────────────


async def satisfies_bucket(
    university: str | None,
    program: str | None,
    course_code: str,
    db: AsyncSession,
    *,
    bucket_name: str | None = None,
):
    """Does ``course_code`` satisfy a requirement bucket in this program?

    Answered from the program's cached ``RequirementRule`` rows — researched once
    from the university's own pages, then reused identically for every student in
    the program. Returns a ``BucketVerdict`` (see
    ``app.services.requirement_rules``) or ``None`` when nothing is cached yet.

    ``None`` is a first-class answer and callers must treat it as "we do not
    know", never as "no". A program whose research has not run yet, or whose
    rules do not mention this course, is a gap in Acadvo's coverage — not a
    statement about the student's degree.

    This does not consult, extend, or create the course catalog. A rule can only
    classify a course that already exists; it can never introduce one. That is
    the structural reason a bad rule cannot become a fabricated course.
    """
    from app.services.requirement_rules import classify_course, get_rules

    rules = await get_rules(university, program, db)
    if not rules:
        return None
    return classify_course(rules, course_code, bucket_name=bucket_name)


def format_prereqs(prerequisites: list[list[str]] | None) -> str:
    """Render a catalog ``prerequisites`` value for a prompt/context line."""
    if not prerequisites:
        return "none"
    groups = ["(" + " OR ".join(group) + ")" for group in prerequisites]
    return " AND ".join(groups)


# ── Shortlisting ─────────────────────────────────────────────────────
#
# `format_allowed_courses` renders the WHOLE catalog into the prompt. That was
# fine while a catalog meant 22 hand-entered York courses; it stops being fine
# the moment one is real. A 1,195-course SFU catalog renders to roughly 20k
# tokens, which is over the per-request token cap on a small account and
# expensive on any account — so growing the catalog, the entire point of the
# ingestion pipeline, silently broke course search and the planner.
#
# So the model gets a shortlist, not the catalog. It still may only choose from
# what it is given, and every code it returns is still validated against the FULL
# catalog afterwards, so shortlisting cannot let a fabricated course through — it
# can only mean a real course was not offered as a candidate. That is the honest
# trade, and it is bounded by making the shortlist generous.

# Roughly 25 tokens per rendered line, so 400 lines is ~10k tokens of candidates.
# Big enough that a plausible course is almost never missed, small enough to sit
# inside a modest per-request budget alongside the rest of the prompt.
DEFAULT_SHORTLIST = 400


def _subject_of(code: str) -> str:
    """"LE/EECS 2030" -> "EECS"; "CMPT 225" -> "CMPT"."""
    head = (code or "").split(" ")[0]
    return head.split("/")[-1].upper()


def _tokenize(text: str) -> set[str]:
    out = set()
    word = ""
    for ch in (text or "").upper():
        if ch.isalnum():
            word += ch
        elif word:
            out.add(word)
            word = ""
    if word:
        out.add(word)
    # One- and two-character fragments match everything and rank nothing.
    return {w for w in out if len(w) > 2}


def _course_number(code: str) -> int | None:
    """The numeric part of a course code, or None."""
    digits = ""
    for ch in (code or ""):
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    try:
        return int(digits) if digits else None
    except ValueError:
        return None


def is_graduate_level(code: str, university: str | None = None) -> bool:
    """True for a course an undergraduate cannot normally take.

    Numbering is per-school but the convention within a school is consistent:
    three-digit codes (SFU's ``CMPT 225``) put graduate work at 700+, four-digit
    codes (York's ``EECS 2030``) at 5000+.

    Pass ``university`` whenever the caller knows it. The width heuristic below
    is a *fallback*, and for at least two schools it is exactly backwards: UofT
    and TMU number undergraduate courses with three digits and graduate ones with
    four (``CSC2515``, ``CP8201``), so the four-digit branch — written for York,
    where 4000 is a senior undergraduate course — waves every one of them through
    as undergraduate. ``program_config.GRADUATE_RULES`` carries the per-school
    rule; only when a school has no entry does the heuristic decide.

    This matters now in a way it did not before. The hand-entered York catalog
    held 22 undergraduate courses, so nothing graduate could be recommended. A
    real ingested catalog contains the whole calendar — SFU's includes BISC 800
    and friends — and the planner cheerfully scheduled them into a first-year
    term. "Take BISC 800 in your first semester" is not a small error to a
    student who trusts it.
    """
    n = _course_number(code)
    if n is None:
        return False

    rule = get_graduate_rule(university)
    if rule:
        digits = len(str(n))
        if "graduate_digits" in rule and digits >= rule["graduate_digits"]:
            return True
        if "min_number" in rule and n >= rule["min_number"]:
            return True
        return False

    if n >= 1000:                 # four-digit numbering (York: 5000+ is graduate)
        return n >= 5000
    # Three-digit numbering: 500+ is graduate. Verified against the ingested SFU
    # catalog rather than assumed — the 500-699 band there is "Graduate Co-op",
    # "Graduate Project", "Master of Environmental Toxicology Project". A 700
    # threshold let 97 graduate courses through, and the planner scheduled them.
    return n >= 500


def undergraduate_only(
    catalog: dict[str, dict], university: str | None = None
) -> dict[str, dict]:
    """Drop graduate-level entries from a catalog.

    ``university`` is optional only so existing hermetic callers keep working;
    every real call site has it, and passing it is what keeps UofT's ``CSC 2515``
    out of an undergraduate's plan.
    """
    return {
        c: e for c, e in catalog.items() if not is_graduate_level(c, university)
    }


def shortlist_for_query(
    catalog: dict[str, dict],
    query: str,
    *,
    exclude: set[str] | None = None,
    limit: int = DEFAULT_SHORTLIST,
) -> dict[str, dict]:
    """Narrow ``catalog`` to the entries most plausibly matching ``query``.

    Lexical, not semantic, and deliberately so: this is a cheap pre-filter whose
    only job is to keep the prompt inside a token budget. The model still does
    the actual matching over what it is handed.

    When nothing matches lexically the whole catalog is out of budget anyway, so
    a capped slice goes through and the model reports no matches — which is the
    truthful outcome for a query with no lexical foothold.
    """
    exclude = exclude or set()
    pool = {c: e for c, e in catalog.items() if c not in exclude}
    if len(pool) <= limit:
        return pool

    tokens = _tokenize(query)
    scored: list[tuple[int, str]] = []
    for code, entry in pool.items():
        haystack = _tokenize(f"{entry.get('course_code', '')} {entry.get('course_name', '')}")
        hits = len(tokens & haystack)
        # A subject-code match ("PSYC 300 level") is a stronger signal than one
        # shared word in a title, so it is weighted above it.
        if _subject_of(code) in tokens:
            hits += 2
        if hits:
            scored.append((hits, code))

    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = [code for _, code in scored[:limit]]
    if len(chosen) < limit:
        # Top up deterministically so the shortlist is stable between runs.
        chosen += [c for c in sorted(pool) if c not in set(chosen)][: limit - len(chosen)]
    return {c: pool[c] for c in chosen}


def shortlist_for_student(
    catalog: dict[str, dict],
    subjects: set[str],
    *,
    program: str | None = None,
    exclude: set[str] | None = None,
    limit: int = DEFAULT_SHORTLIST,
) -> dict[str, dict]:
    """Narrow ``catalog`` to what a student in ``subjects`` might actually take.

    Used where there is no query — the semester planner and the recommendation
    generator. Courses in the student's own subject areas come first (that is
    what their degree is made of), then anything whose subject or title matches
    their ``program``, then everything else in code order.

    That middle tier exists because of a real failure: a brand-new Psychology
    student has no courses yet, so ``subjects`` is empty, and a plain alphabetical
    fallback handed the planner BISC and BPK — it produced a Psychology degree
    plan made of biology courses. Ordering by relevance to the program name is
    what a person would do with the same list.
    """
    exclude = exclude or set()
    pool = {c: e for c, e in catalog.items() if c not in exclude}
    if len(pool) <= limit:
        return pool

    subjects = {s.upper() for s in subjects}
    program_tokens = _tokenize(program or "")

    own, related, rest = [], [], []
    for code in sorted(pool):
        subject = _subject_of(code)
        if subject in subjects:
            own.append(code)
            continue
        title_tokens = _tokenize(pool[code].get("course_name", ""))
        # "PSYC" is a prefix of "PSYCHOLOGY", which is how a subject code relates
        # to its program name almost everywhere.
        subject_matches = any(
            t.startswith(subject) or subject.startswith(t[:4])
            for t in program_tokens
            if len(t) >= 4
        )
        if subject_matches or (program_tokens & title_tokens):
            related.append(code)
        else:
            rest.append(code)

    chosen = (own + related + _spread_by_subject(rest))[:limit]
    return {c: pool[c] for c in chosen}


def _spread_by_subject(codes: list[str]) -> list[str]:
    """Interleave codes so one subject cannot monopolise a truncated tail.

    The tail of the shortlist is where electives come from, and sorted order
    means it starts at the alphabetical beginning of the catalog and stops
    wherever the budget runs out. On the full SFU catalog that gave a French
    major a plan whose every elective was BISC — not because biology suited
    them, but because "B" comes early and the list was cut off before the rest
    of the alphabet. Round-robin over subjects shows the model a spread of what
    the university actually offers.
    """
    by_subject: dict[str, list[str]] = {}
    for code in codes:
        by_subject.setdefault(_subject_of(code), []).append(code)
    out: list[str] = []
    subjects = sorted(by_subject)
    while subjects:
        for subject in list(subjects):
            bucket = by_subject[subject]
            if bucket:
                out.append(bucket.pop(0))
            else:
                subjects.remove(subject)
    return out


def allowed_courses_budget_chars(share: float = 0.4) -> int:
    """How much of a prompt the ALLOWED COURSES block may occupy, in characters.

    A real catalog does not fit in a prompt: SFU's 1,195 courses render to ~93k
    characters (~23k tokens), which is over the per-request token cap on a small
    account and wasteful on a large one. When ``GROQ_MAX_REQUEST_TOKENS`` names a
    ceiling, the course list gets 40% of it — the rest is the student's
    transcript, requirements, instructions, and the completion itself. With no
    ceiling configured, a fixed cap still applies, because "the catalog grew and
    every AI call started failing" is not a failure mode worth keeping.

    ``share`` is lower for callers whose *output* is large. Search returns eight
    lines of JSON and can spend its budget on candidates; the semester planner
    writes several terms of structured JSON and needs that room left over, so it
    asks for a smaller slice of the same ceiling.
    """
    ceiling = settings.GROQ_MAX_REQUEST_TOKENS
    tokens = int(ceiling * share) if ceiling > 0 else 12000
    return tokens * 4  # ~4 characters per token


def format_allowed_courses(
    catalog: dict[str, dict],
    exclude: set[str] | None = None,
    *,
    max_chars: int | None = None,
    ordered: bool = False,
) -> str:
    """Render the catalog as an ALLOWED-course list for grounding the LLM.

    Each line: ``- CODE | Name | X.X cr | prereqs: ... | gate: SCOPE GPA ≥ MIN``.
    Codes in ``exclude`` (already completed / in plan) are omitted."""
    exclude = exclude or set()
    if max_chars is None:
        max_chars = allowed_courses_budget_chars()
    # Ranked input (a shortlist) is rendered in its own order so that if the
    # budget truncates, what falls off the end is the least relevant candidate
    # rather than everything after "M".
    codes = list(catalog) if ordered else sorted(catalog)
    lines = []
    used = 0
    for code in codes:
        if code in exclude:
            continue
        entry = catalog[code]
        parts = [
            f"- {entry['course_code']}",
            entry["course_name"],
            f"{entry['credits']} cr",
            f"prereqs: {format_prereqs(entry.get('prerequisites'))}",
        ]
        gate = entry.get("gpa_gate")
        if gate:
            parts.append(f"gate: {gate.get('scope', '')} GPA ≥ {float(gate.get('min', 4.5)):.2f}")
        line = " | ".join(parts)
        if max_chars and used + len(line) + 1 > max_chars:
            break
        used += len(line) + 1
        lines.append(line)
    return "\n".join(lines) or "  (no catalog courses available)"
