"""Adapter for the University of British Columbia's calendar JSON:API.

UBC runs its calendars on Drupal and exposes the standard read-only JSON:API,
the same shape as UofT's divisional calendars:

    GET https://{host}/jsonapi/node/course?page[limit]=50   -> a page of courses
    (follow ``links.next`` until it is absent)

Both undergraduate calendars are covered, one host each — see ``CAMPUSES``. The
stock Drupal ``robots.txt`` on each blocks only ``/core/``, ``/profiles/``,
README files and the authenticated ``/user/*`` paths, so the calendar and its API
are permitted.

**The campus marker is not decoration.** UBC writes the campus into the subject
code itself — ``CPSC_V`` is Vancouver, ``CPSC_O`` is Okanagan — and the two
campuses share **591** subject-and-number pairs that are *different courses*:
Vancouver's ``SPAN 201`` is "Elementary Spanish I", Okanagan's is "Advanced
Beginners' Spanish I"; ``HIST 308`` is Quebec history at one and the Scientific
Revolution at the other. Stripping ``_V``/``_O`` to get a tidier code would merge
all 591 pairs and hand students another campus's course, which is exactly the
bug that truncating ``CSC148H1`` caused at UofT. So UBC's own notation is kept
verbatim, and ``services/catalog.Catalog`` resolves a student's bare ``CPSC 100``
to the Vancouver row deterministically.

**Credits are published**, unlike Waterloo's API: ``field_course_credit`` carries
them as a parenthesised string — ``(3)``, ``(1.5)``, ``(0)``, or a range like
``(3-6)`` for variable-credit courses. A range is stored at its LOWER bound, so a
plan under-counts rather than over-counts and a student is never told they have
more credits than they earned.

**Prerequisites are prose, and only sometimes present.** There is no
prerequisite field in the schema; UBC states them inside
``field_course_description`` ("Prerequisite: One of CPSC 110, CPSC 103."). The
sentence is extracted and parsed, so what comes out is best-effort: a course
whose description omits them simply gets none, which leaves advice unhelpful
rather than wrong.
"""
from __future__ import annotations

import html
import logging
import re
import time

import httpx

from app.ingest.prereq_parser import parse_prerequisites
from app.ingest.store import CatalogRow

logger = logging.getLogger("acadvo.ingest.ubc")

UNIVERSITY = "University of British Columbia"
SOURCE = "ubc_calendar_jsonapi"

# Campus -> calendar host. Each is a separate Drupal site.
CAMPUSES: dict[str, str] = {
    "vancouver": "vancouver.calendar.ubc.ca",
    "okanagan": "okanagan.calendar.ubc.ca",
}

_PAGE_SIZE = 50
_MAX_PAGES = 600

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# "CPSC_V - 100: Computational Thinking" / "MATH_O - 100A: Title"
_TITLE_RE = re.compile(
    r"^(?P<subject>[A-Za-z]{2,5})(?P<campus>_[A-Za-z])?\s*-\s*"
    r"(?P<number>\d{3,4}[A-Za-z]?)\s*:?\s*(?P<name>.*)$"
)

# "(3)", "(1.5)", "(3-6)", "(0)"
_CREDIT_RE = re.compile(r"\(\s*(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?\s*)?\)")

# UBC states prerequisites inside the description. Stop at the next sentence that
# starts another labelled clause, so a Corequisite or Equivalency sentence does
# not get swallowed into the prerequisite expression.
_PREREQ_RE = re.compile(
    r"Prerequisite[s]?\s*:\s*(?P<body>.*?)"
    r"(?=(?:Coreq|Corequisite|Equivalency|Equivalent|Recommended|Note)\b|$)",
    re.IGNORECASE | re.DOTALL,
)

_DEFAULT_CREDITS = 3.0


def _text(field) -> str:
    """Flatten a Drupal text field to plain text."""
    if not field:
        return ""
    value = field.get("value") if isinstance(field, dict) else field
    if not isinstance(value, str):
        return ""
    value = re.sub(r"href=['\"][^'\"]*['\"]", " ", value)
    value = _TAG_RE.sub(" ", value)
    return _WS_RE.sub(" ", html.unescape(value)).strip()


def _credits(raw) -> float:
    """``"(3)"`` -> 3.0; ``"(3-6)"`` -> 3.0 (the lower bound of a range).

    Lower bound on purpose: a variable-credit course counted at its maximum would
    tell a student they are closer to graduating than they are.
    """
    m = _CREDIT_RE.search(str(raw or ""))
    if not m:
        return _DEFAULT_CREDITS
    try:
        return float(m.group(1))
    except ValueError:
        return _DEFAULT_CREDITS


def _prerequisites(description: str, campus: str = "") -> list[list[str]]:
    """Pull the prerequisite sentence out of the description and parse it.

    ``campus`` ("_V"/"_O") qualifies the codes that come back. UBC states
    prerequisites bare — "One of CPSC 110, CPSC 103" — and inside the Okanagan
    calendar those mean the Okanagan courses. Left bare they would resolve to
    Vancouver's, so an Okanagan student could be told they had met a requirement
    with a course from a campus they do not attend.
    """
    if not description:
        return []
    m = _PREREQ_RE.search(description)
    if not m:
        return []
    groups = parse_prerequisites(m.group("body"))
    if not campus:
        return groups
    return [[_qualify(code, campus) for code in group] for group in groups]


def _qualify(code: str, campus: str) -> str:
    """``("CPSC 103", "_O")`` -> ``"CPSC_O 103"``; already-marked codes unchanged."""
    subject, _, rest = code.partition(" ")
    if "_" in subject or not rest:
        return code
    return f"{subject}{campus} {rest}"


def _parse_title(title: str) -> tuple[str, str, str] | None:
    """``"CPSC_V - 100: Computational Thinking"`` ->
    ``("CPSC_V 100", "CPSC", "Computational Thinking")``."""
    m = _TITLE_RE.match((title or "").strip())
    if not m:
        return None
    subject = m.group("subject").upper()
    campus = (m.group("campus") or "").upper()
    code = f"{subject}{campus} {m.group('number').upper()}"
    return code, subject, (m.group("name") or "").strip()


def fetch_courses(
    campuses: list[str] | None = None,
    *,
    throttle: float = 0.2,
) -> list[CatalogRow]:
    """Walk both UBC calendars and return catalog rows."""
    wanted = campuses or list(CAMPUSES)
    rows: list[CatalogRow] = []
    seen: set[str] = set()

    with httpx.Client(headers={"User-Agent": "acadvo-catalog-ingest"}) as client:
        for key in wanted:
            host = CAMPUSES.get(key)
            if not host:
                logger.warning("Unknown UBC campus %r — skipping", key)
                continue
            rows.extend(_fetch_campus(client, host, seen, throttle))

    logger.info("UBC: fetched %d courses across %s", len(rows), ", ".join(wanted))
    return rows


def _fetch_campus(
    client: httpx.Client, host: str, seen: set[str], throttle: float
) -> list[CatalogRow]:
    url = (
        f"https://{host}/jsonapi/node/course"
        "?fields%5Bnode--course%5D=title,field_course_credit,field_course_description"
        f"&page%5Blimit%5D={_PAGE_SIZE}"
    )
    rows: list[CatalogRow] = []
    pages = 0

    while url and pages < _MAX_PAGES:
        pages += 1
        try:
            resp = client.get(url, timeout=60.0)
        except httpx.HTTPError as exc:
            logger.warning("UBC fetch failed for %s: %s", url, exc)
            break
        if resp.status_code != 200:
            logger.warning("UBC %s returned HTTP %s", url, resp.status_code)
            break
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("UBC %s returned non-JSON", url)
            break

        for node in payload.get("data") or []:
            row = _row_from_node(node)
            if row is None:
                continue
            if row["course_code"] in seen:
                continue
            seen.add(row["course_code"])
            rows.append(row)

        url = ((payload.get("links") or {}).get("next") or {}).get("href")
        if url and throttle:
            time.sleep(throttle)

    if pages >= _MAX_PAGES:
        logger.warning("UBC %s hit the %d-page ceiling; results may be partial", host, _MAX_PAGES)
    logger.info("UBC %s: %d courses over %d page(s)", host, len(rows), pages)
    return rows


def _row_from_node(node) -> CatalogRow | None:
    if not isinstance(node, dict):
        return None
    attrs = node.get("attributes") or {}
    parsed = _parse_title(attrs.get("title") or "")
    if not parsed:
        return None
    code, subject, name = parsed
    campus = code.partition(" ")[0][len(subject):]  # "_V" / "_O" / "" 
    if not name:
        # A title with no course name is a malformed calendar row (the live feed
        # carries a couple, e.g. "- 447:"). Inventing a name for it would put a
        # course in the catalog that UBC never described.
        return None

    description = _text(attrs.get("field_course_description"))
    return CatalogRow(
        course_code=code,
        course_name=name[:255],
        credits=_credits(attrs.get("field_course_credit")),
        subject_faculty=subject,
        prerequisites=_prerequisites(description, campus),
        gpa_gate=None,
    )
