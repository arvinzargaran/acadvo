"""Adapter for the University of Toronto's calendar JSON:API.

UofT publishes each divisional calendar as a Drupal site, and those sites expose
Drupal's standard, read-only **JSON:API** — a documented interface, on hosts whose
`robots.txt` permits it (the stock Drupal file blocks only `/core/`, `/profiles/`,
README files and the authenticated `/user/*` paths):

    GET https://{host}/jsonapi/node/courses?page[limit]=50   -> a page of courses
    (follow ``links.next`` until it is absent)

This is what `SOURCES.md` was missing. The entry there concluded that UofT had no
sanctioned source because the *Timetable Builder* backend
(`api.easi.utoronto.ca`) is an undocumented private API and `data.utoronto.ca`
carries only institutional statistics. Both remain true — and neither is needed.
The calendars are the authoritative statement of what a course is, they are
public, and JSON:API is a first-class published interface rather than a scrape of
someone's markup.

Three undergraduate divisions are covered, one host each — see ``CAMPUSES``. A
course's campus is written into its own code (``CSC207H1`` St. George,
``CSC207H5`` UTM, ``CSC207H3`` UTSC), so all three can share one catalog without
colliding.

**Credits are read off the code, not guessed.** UofT encodes the weight in the
suffix: ``H`` is a half course (0.5) and ``Y`` a full course (1.0). That is a
published, load-bearing convention — the same one students read off their own
transcripts — so unlike Waterloo (whose API omits weights entirely) no default is
needed here.
"""
from __future__ import annotations

import html
import logging
import re
import time

import httpx

from app.ingest.prereq_parser import parse_prerequisites
from app.ingest.store import CatalogRow

logger = logging.getLogger("acadvo.ingest.uoft")

UNIVERSITY = "University of Toronto"
SOURCE = "uoft_calendar_jsonapi"

# Division -> calendar host. Each is a separate Drupal site with its own courses.
CAMPUSES: dict[str, str] = {
    "artsci": "artsci.calendar.utoronto.ca",   # Faculty of Arts & Science (St. George)
    "utm": "utm.calendar.utoronto.ca",         # UofT Mississauga
    "utsc": "utsc.calendar.utoronto.ca",       # UofT Scarborough
}

_PAGE_SIZE = 50
# A stop so a pagination bug cannot walk forever against someone else's server.
_MAX_PAGES = 400

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# St. George / UTM: subject letters, number, weight suffix (H/Y), campus digit —
# "CSC207H1".
_CODE_RE = re.compile(r"^([A-Za-z]{2,5})\s*(\d{3,4})([A-Za-z])?(\d)?$")

# UTSC: subject letters, a LEVEL letter (A-D, the year of study), only two
# digits, weight, campus — "CSCA08H3". Matched first, because the general
# pattern above reads the level letter as part of the subject and then fails on
# the two-digit number. That is why an earlier UTSC run fetched 44 pages and
# produced zero rows: every single course was silently rejected as unparseable.
_UTSC_RE = re.compile(r"^([A-Za-z]{3})\s*([A-Za-z]\d{2})([A-Za-z])(\d)$")

# UofT's published course weights, from the suffix in the code itself.
_WEIGHTS = {"H": 0.5, "Y": 1.0}
_DEFAULT_WEIGHT = 0.5


def _text(field) -> str:
    """Flatten one of Drupal's text fields to plain text.

    Calendar prose is stored as HTML with the referenced courses as links, so the
    tags have to come off before the prerequisite parser sees it — otherwise an
    href like ``/course/CSC148H1`` contributes its own copy of the code.
    """
    if not field:
        return ""
    value = field.get("value") if isinstance(field, dict) else field
    if not isinstance(value, str):
        return ""
    # Drop hrefs wholesale first: the anchor text carries the code already.
    value = re.sub(r"href=['\"][^'\"]*['\"]", " ", value)
    value = _TAG_RE.sub(" ", value)
    return _WS_RE.sub(" ", html.unescape(value)).strip()


def _prereq_text(field) -> str:
    """Prerequisite prose, with UofT's ``/`` alternation spelled out.

    UofT writes alternatives with a slash — "CSC148H1/ CSC148H5" means either one
    satisfies the requirement. The shared parser understands ``and``/``or``/commas
    but not slashes, and it is deliberately not taught to: York writes its faculty
    prefix with a slash too (``LE/EECS 2101``), so a global rule would split York's
    codes in half. Doing it here keeps the change where the convention lives.
    """
    text = _text(field)
    return text.replace("/", " or ") if text else ""


def _parse_code(title: str) -> tuple[str, str, float] | None:
    """``"CSC207H1"`` -> ``("CSC 207H1", "CSC", 0.5)``; ``"CSCA08H3"`` ->
    ``("CSC A08H3", "CSC", 0.5)``. None if unrecognizable.

    The subject is the first three letters for UTSC, never the level letter with
    them: ``CSCA08H3``, ``CSCB09H3`` and ``CSCC01H3`` are first-, second- and
    third-year Computer Science, and splitting them as ``CSCA``/``CSCB``/``CSCC``
    would fragment one subject into four and break the coverage check that tells
    a student whether their program is in the catalog at all.
    """
    title = (title or "").strip()
    m = _UTSC_RE.match(title)
    if m:
        subject = m.group(1).upper()
        number = f"{m.group(2).upper()}{m.group(3).upper()}{m.group(4)}"
        credits = _WEIGHTS.get(m.group(3).upper(), _DEFAULT_WEIGHT)
        return f"{subject} {number}", subject, credits

    m = _CODE_RE.match(title)
    if not m:
        return None
    subject, number, weight, campus = m.group(1).upper(), m.group(2), m.group(3), m.group(4)
    code = f"{subject} {number}{(weight or '').upper()}{campus or ''}"
    credits = _WEIGHTS.get((weight or "").upper(), _DEFAULT_WEIGHT)
    return code, subject, credits


def fetch_courses(
    campuses: list[str] | None = None,
    *,
    throttle: float = 0.2,
) -> list[CatalogRow]:
    """Walk the calendar JSON:API for each campus and return catalog rows.

    ``campuses`` are keys of :data:`CAMPUSES`; ``None`` fetches all three.
    ``throttle`` is the polite delay between page requests.
    """
    wanted = campuses or list(CAMPUSES)
    rows: list[CatalogRow] = []
    seen: set[str] = set()

    with httpx.Client(headers={"User-Agent": "acadvo-catalog-ingest"}) as client:
        for key in wanted:
            host = CAMPUSES.get(key)
            if not host:
                logger.warning("Unknown UofT campus %r — skipping", key)
                continue
            rows.extend(_fetch_campus(client, host, seen, throttle))

    logger.info("UofT: fetched %d courses across %s", len(rows), ", ".join(wanted))
    return rows


def _fetch_campus(
    client: httpx.Client, host: str, seen: set[str], throttle: float
) -> list[CatalogRow]:
    url = f"https://{host}/jsonapi/node/courses?page%5Blimit%5D={_PAGE_SIZE}"
    rows: list[CatalogRow] = []
    pages = 0

    while url and pages < _MAX_PAGES:
        pages += 1
        try:
            resp = client.get(url, timeout=60.0)
        except httpx.HTTPError as exc:
            logger.warning("UofT fetch failed for %s: %s", url, exc)
            break
        if resp.status_code != 200:
            logger.warning("UofT %s returned HTTP %s", url, resp.status_code)
            break
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("UofT %s returned non-JSON", url)
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
        logger.warning("UofT %s hit the %d-page ceiling; results may be partial", host, _MAX_PAGES)
    logger.info("UofT %s: %d courses over %d page(s)", host, len(rows), pages)
    return rows


def _row_from_node(node) -> CatalogRow | None:
    if not isinstance(node, dict):
        return None
    attrs = node.get("attributes") or {}
    parsed = _parse_code(attrs.get("title") or "")
    if not parsed:
        return None
    code, subject, credits = parsed

    name = _text(attrs.get("field_course_title")) or code
    return CatalogRow(
        course_code=code,
        course_name=name[:255],
        credits=credits,
        subject_faculty=subject,
        prerequisites=parse_prerequisites(_prereq_text(attrs.get("field_prerequisite"))),
        gpa_gate=None,
    )
