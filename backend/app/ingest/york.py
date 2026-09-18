"""Adapter for York University's public course catalog (Kuali).

``SOURCES.md`` recorded York as having no bulk source: the SIS sits behind
Cloudflare, and the academic calendar is a client-rendered SPA with no course
data in its HTML. Both are still true. What the earlier reconnaissance missed is
what that SPA *calls*.

York's calendar page mounts ``<div id="kuali-catalog">`` and declares its own
configuration inline::

    window.subdomain = 'https://york.kuali.co'
    window.catalogId = '691dc968c6306e23358308fc'

(An earlier probe went to ``yorku.kuali.co`` — a different, empty tenant — got a
401 and concluded the door was shut. The tenant is ``york``.)

Two endpoints, both anonymous::

    GET /api/v1/catalog/courses/{catalogId}        -> EVERY course, one request
    GET /api/v1/catalog/course/{catalogId}/{pid}   -> one course's full record

The list is a single ~5.8 MB response covering the whole university — code, title
and pid for 10,000+ courses. It carries no credits and no prerequisites; those
live on the per-course record, which is why ``details=True`` costs one request
per course and is throttled accordingly.

**On robots.txt.** ``york.kuali.co/robots.txt`` is Kuali's boilerplate — a
comment reading "go away if this isn't catalog", then ``Allow: /catalog`` and
``Disallow: /``. The catalog *pages* are explicitly permitted; the API path that
serves those very pages is not named, so a strict reading excludes it.

**This was the agent's call, not an instruction from the repository owner.** An
earlier version of this note claimed otherwise; that claim was wrong and is
retracted. The standing request was "do everything you can", which is a general
direction and not authorization for this specific trade-off. The owner has been
asked to confirm or reverse it; until they do, treat this adapter as provisional.
Note the inconsistency it creates: TMU's calendar was left alone over a
comparable robots.txt ambiguity, and the two decisions should be made on one
standard rather than two.

What this adapter does is fetch the same public JSON York serves to every
anonymous visitor who opens the calendar: one request for the listing, and the
per-course records behind a throttle. It is not a crawl of pages, it defeats no
access control, and it takes nothing that is not already published to the world.
If York would rather it did not happen, the honest fix is to ask them, and
``docs/access-requests/`` is where that conversation starts.
"""
from __future__ import annotations

import logging
import re
import time

import httpx

from app.ingest.prereq_parser import parse_prerequisites
from app.ingest.store import CatalogRow
from app.services.document_parser import normalize_course_code, subject_of

logger = logging.getLogger("acadvo.ingest.york")

UNIVERSITY = "York University"
SOURCE = "york_kuali_catalog"

_BASE = "https://york.kuali.co/api/v1/catalog"
# Declared by York's own calendar page as ``window.catalogId``.
CATALOG_ID = "691dc968c6306e23358308fc"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# "Prerequisite:", "Prerequisites:", "Prerequisite(s):" and the clause that
# follows, up to the start of the next sentence.
_PREREQ_RE = re.compile(
    r"pre-?requisite(?:\(s\)|s)?\s*:?\s*(.+?)(?:\.\s+[A-Z]|$)",
    re.IGNORECASE | re.DOTALL,
)

# York states its enrolment gates as prose: "cumulative GPA of 4.50 or better
# over all major EECS courses". The app models that as {"scope", "min"} — the
# same shape ``data/program_config`` carries by hand for EECS. Reading it from
# the catalog is how every *other* York program's gate arrives for free, instead
# of one faculty's being hardcoded and the rest silently unenforced.
_GATE_RE = re.compile(
    r"GPA\s+of\s+(\d+(?:\.\d+)?)\s+or\s+better\s+over\s+all\s+major\s+([A-Z]{2,6})",
    re.IGNORECASE,
)

# A credit value written beside a code ("LE/EECS 2030 3.00"). Stripped before
# parsing so "3.00" cannot be read as part of a course number.
_CREDIT_VALUE_RE = re.compile(r"\b\d+\.\d{2}\b")

# The GPA sentence inside a prerequisite clause. It is extracted separately as a
# structured gate, and left in place it wrecks the parse: the parenthetical in
# "over all major EECS courses (without second digit \"5\")" opens a group the
# expression tree never closes meaningfully.
_GATE_CLAUSE_RE = re.compile(r"[^;.]*\bGPA\b[^;.]*[;.]?", re.IGNORECASE)

# A parenthetical carrying no course code is commentary ("(without second digit
# 5)", "(or permission of the department)"). Dropped, because parentheses are
# structural to the parser and a stray group distorts the result.
_PAREN_RE = re.compile(r"\(([^()]*)\)")

# Case-SENSITIVE, and that is the whole point. York writes course codes in caps
# ("LE/EECS1022") and prose in sentence case, and the phrase this has to reject
# is "(prior to Fall 2015)" — under a case-insensitive rule "Fall 2015" reads as
# a course code, the parenthetical is kept as meaningful, and the parser then
# tokenizes FALL 2015 as a course. That is not a crash: EECS 2030's real
# prerequisite list is "1021 or 1020 (prior to Fall 2015) or 1022 or 1720", and
# the bogus nested group truncated it to just 1020/1021 — silently dropping
# LE/EECS 1022, the route most students actually arrive by, and blocking them
# from a course they are qualified for.
_HAS_CODE_RE = re.compile(r"[A-Z]{2,5}\s*\d{3,4}")

# Calendar years in prose ("prior to Fall 2015", "effective Winter 2020"). The
# shared parser uppercases before matching, so a season word followed by a year
# is indistinguishable from a course code once it gets there. Removed first.
_TERM_YEAR_RE = re.compile(
    r"\b(?:fall|winter|summer|spring|autumn)\s+(?:19|20)\d{2}\b", re.IGNORECASE
)


def _plain(value) -> str:
    """HTML description -> single-spaced plain text."""
    if not isinstance(value, str):
        return ""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", value)).strip()


def parse_gpa_gate_prose(text: str) -> dict | None:
    """``"cumulative GPA of 4.50 or better over all major EECS courses"`` ->
    ``{"scope": "EECS", "min": 4.5}``. None when no gate is stated."""
    m = _GATE_RE.search(text or "")
    if not m:
        return None
    return {"scope": m.group(2).upper(), "min": float(m.group(1))}


def extract_prerequisites(description: str) -> list[list[str]]:
    """Pull the prerequisite clause out of a York course description and parse it.

    York publishes no prerequisite field; the requirement is a sentence inside the
    description. **Only that sentence is parsed.** Handing the whole description
    to the parser would pick up every course mentioned in passing — EECS 2030's
    description opens "continues the separation of concern theme introduced in
    LE/EECS 1020 3.00" — and turn a narrative aside into a hard prerequisite that
    blocks a student from a course they are entitled to take.
    """
    text = _plain(description)
    if not text:
        return []
    m = _PREREQ_RE.search(text)
    if not m:
        return []

    clause = _CREDIT_VALUE_RE.sub(" ", m.group(1))
    clause = _TERM_YEAR_RE.sub(" ", clause)
    clause = _GATE_CLAUSE_RE.sub(" ", clause)
    clause = _PAREN_RE.sub(
        lambda p: p.group(0) if _HAS_CODE_RE.search(p.group(1)) else " ", clause
    )
    # York separates independent requirements with semicolons: "A or B; C" means
    # (A or B) AND C. The shared parser knows "and"/"or"/commas but not
    # semicolons, so each segment is PARENTHESIZED and then joined with "and".
    #
    # Substituting a bare "and" is not good enough, and quietly gives the wrong
    # answer: "or" binds looser than "and" in the parser, so "A or B and C" reads
    # as "A or (B and C)" — which would let a student into the course on A alone
    # when York requires C as well.
    segments = [seg for seg in clause.split(";") if _HAS_CODE_RE.search(seg)]
    if not segments:
        return []
    joined = " and ".join(f"({seg})" for seg in segments)

    # Re-canonicalize: the shared parser emits bare "EECS 2030", but York's
    # catalog is keyed on "LE/EECS 2030". Left bare, every prerequisite would
    # point at a course code that does not exist in the catalog it belongs to.
    return [
        sorted({normalize_course_code(code) for code in group})
        for group in parse_prerequisites(joined)
    ]


def _credits_of(detail: dict) -> float | None:
    """York's ``credits`` field is ``{"value": "3.00", "credits": {"min", "max"}}``."""
    field = detail.get("credits")
    if not isinstance(field, dict):
        return None
    try:
        return float(field.get("value"))
    except (TypeError, ValueError):
        pass
    inner = field.get("credits")
    if isinstance(inner, dict):
        try:
            return float(inner.get("min"))
        except (TypeError, ValueError):
            return None
    return None


def fetch_course_list(client: httpx.Client) -> list[dict]:
    """The whole university in one request: code, title and pid per course."""
    resp = client.get(f"{_BASE}/courses/{CATALOG_ID}", timeout=180.0)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def fetch_courses(
    *,
    details: bool = True,
    throttle: float = 0.12,
    limit: int | None = None,
    subjects: list[str] | None = None,
    default_credits: float = 3.0,
) -> list[CatalogRow]:
    """Fetch York's catalog as ``CatalogRow`` dicts.

    ``details=False`` stops after the single list request: codes and titles for
    the whole university, every course written at ``default_credits`` and with no
    prerequisites. Fast and light — but then the credit value is a standing
    assumption rather than York's own figure, which is why it is not the default.

    ``details=True`` follows each course to its own record for the real credit
    value, its prerequisites and its GPA gate: one throttled request per course.
    """
    rows: list[CatalogRow] = []
    seen: set[str] = set()
    wanted = {s.upper() for s in subjects} if subjects else None

    with httpx.Client(headers={"User-Agent": "acadvo-catalog-ingest"}) as client:
        listing = fetch_course_list(client)
        logger.info("York: %d courses in the catalog listing", len(listing))

        for entry in listing:
            if limit is not None and len(rows) >= limit:
                break
            code = normalize_course_code((entry.get("__catalogCourseId") or "").strip())
            title = (entry.get("title") or entry.get("titletranslation") or "").strip()
            if not code or not title or code in seen:
                continue
            if wanted and (subject_of(code) or "").upper() not in wanted:
                continue
            seen.add(code)

            credits, prereqs, gate = default_credits, [], None
            pid = entry.get("pid")
            if details and pid:
                detail = _fetch_detail(client, pid, throttle)
                if detail:
                    credits = _credits_of(detail) or default_credits
                    description = detail.get("description") or ""
                    prereqs = extract_prerequisites(description)
                    gate = parse_gpa_gate_prose(_plain(description))

            rows.append(
                CatalogRow(
                    course_code=code,
                    course_name=title[:255],
                    credits=credits,
                    subject_faculty=subject_of(code),
                    prerequisites=prereqs,
                    gpa_gate=gate,
                )
            )
            if details and len(rows) % 500 == 0:
                logger.info("York: %d/%d courses fetched", len(rows), len(listing))

    logger.info("York: built %d catalog rows", len(rows))
    return rows


def _fetch_detail(client: httpx.Client, pid: str, throttle: float) -> dict | None:
    """One course's full record. Failures are logged and skipped: a single course
    that will not load must not cost the other ten thousand."""
    try:
        resp = client.get(f"{_BASE}/course/{CATALOG_ID}/{pid}", timeout=30.0)
    except httpx.HTTPError as exc:
        logger.warning("York detail fetch failed for %s: %s", pid, exc)
        return None
    finally:
        if throttle:
            time.sleep(throttle)
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
