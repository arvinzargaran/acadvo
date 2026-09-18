"""Adapter for the University of Waterloo's official Open Data API (v3).

Waterloo publishes a documented, sanctioned REST API — the same category of
source as SFU's course outlines, and the only other one found across the schools
surveyed in ``SOURCES.md``. It differs from SFU in one respect that matters: it
requires an API key.

    terms      GET /v3/Terms                    -> every term, with termCode
    current    GET /v3/Terms/current            -> the term in progress
    courses    GET /v3/Courses/{termCode}       -> EVERY course in that term
    subject    GET /v3/Courses/{termCode}/{subj}-> one subject's courses

One request returns the whole term, so unlike the SFU crawl (four nested calls
per course) this is a single fetch and needs no throttle.

Auth: an ``X-API-KEY`` header. Keys are free and self-serve, but registration
POSTs an email address to Waterloo and confirms it, so it is the operator's to
do, not this code's. Set ``WATERLOO_API_KEY`` in the environment.
Docs: https://openapi.data.uwaterloo.ca/api-docs/  (getting started:
https://github.com/uWaterloo/OpenData/wiki/Home---Getting-Started)

**On credits.** The v3 ``Course`` schema publishes no unit or credit field —
verified against the live OpenAPI document, which carries 19 properties and not
one of them is a course weight. Rather than invent a per-course number, every
row is written at Waterloo's standard one-term course weight (0.5 units, from
``data.credit_models.COURSE_UNITS``) and this is stated plainly here and in the
CLI output. The consequence is bounded and known: the minority of courses that
are 0.25 or 1.0 units will read as 0.5, so a plan's unit total can be slightly
off, while course identity, titles and prerequisites — what advising actually
turns on — are exactly what Waterloo published. The alternative, guessing weights
per course, would put fabricated numbers in the one table this pipeline exists to
keep honest.
"""
from __future__ import annotations

import logging

import httpx

from app.data.credit_models import COURSE_UNITS
from app.ingest.prereq_parser import parse_prerequisites
from app.ingest.store import CatalogRow

logger = logging.getLogger("acadvo.ingest.waterloo")

UNIVERSITY = "University of Waterloo"
SOURCE = "uwaterloo_open_data_v3"
_BASE = "https://openapi.data.uwaterloo.ca/v3"

# Waterloo's standard one-term course weight. Not from the API — see the note in
# the module docstring — but from the registrar's published unit, and shared with
# the credit model so the planner and the catalog never disagree.
STANDARD_UNITS = COURSE_UNITS[UNIVERSITY]

# Undergraduate only. The API mixes graduate offerings into the same term feed
# and marks them here; recommending a grad course to an undergrad is a concrete
# advising failure, not a cosmetic one.
_UNDERGRAD_CAREER = "UG"


class WaterlooAuthError(RuntimeError):
    """No usable API key. Raised instead of returning zero courses, because an
    empty result is indistinguishable from "Waterloo published nothing" and would
    be upserted as a successful ingest of nothing."""


def _get(client: httpx.Client, path: str) -> list | dict | None:
    try:
        resp = client.get(f"{_BASE}{path}", timeout=60.0)
    except httpx.HTTPError as exc:
        logger.warning("Waterloo fetch failed for %s: %s", path, exc)
        return None
    if resp.status_code in (401, 403):
        raise WaterlooAuthError(
            "Waterloo's Open Data API rejected the key (HTTP "
            f"{resp.status_code}). Set WATERLOO_API_KEY to a valid key — register "
            "one at https://openapi.data.uwaterloo.ca/api-docs/ (POST /v3/account/register)."
        )
    if resp.status_code != 200:
        logger.warning("Waterloo %s returned HTTP %s", path, resp.status_code)
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning("Waterloo %s returned non-JSON", path)
        return None


def current_term(api_key: str) -> str | None:
    """The termCode of the term in progress (e.g. "1259"), or None."""
    with httpx.Client(headers=_headers(api_key)) as client:
        data = _get(client, "/Terms/current")
    if isinstance(data, list):
        data = data[0] if data else None
    return (data or {}).get("termCode") if isinstance(data, dict) else None


def _headers(api_key: str) -> dict:
    return {"X-API-KEY": api_key, "User-Agent": "acadvo-catalog-ingest"}


def fetch_courses(
    term: str,
    api_key: str,
    subjects: list[str] | None = None,
) -> list[CatalogRow]:
    """Fetch Waterloo's catalog for ``term`` (a termCode like "1259").

    ``subjects`` (e.g. ["CS", "MATH"]) restricts the ingest to those subject
    codes; ``None`` takes the whole term in one request.
    """
    if not api_key:
        raise WaterlooAuthError(
            "WATERLOO_API_KEY is not set. Waterloo's Open Data API requires a "
            "key; register one at https://openapi.data.uwaterloo.ca/api-docs/."
        )

    with httpx.Client(headers=_headers(api_key)) as client:
        if subjects:
            raw: list = []
            for subj in subjects:
                got = _get(client, f"/Courses/{term}/{subj.strip().upper()}")
                if got:
                    raw.extend(got)
        else:
            raw = _get(client, f"/Courses/{term}") or []

    if not isinstance(raw, list):
        logger.warning("Waterloo returned an unexpected payload for %s", term)
        return []

    rows: list[CatalogRow] = []
    seen: set[str] = set()
    for c in raw:
        if not isinstance(c, dict):
            continue
        career = (c.get("associatedAcademicCareer") or "").upper()
        if career and career != _UNDERGRAD_CAREER:
            continue
        subject = (c.get("subjectCode") or "").strip().upper()
        number = (c.get("catalogNumber") or "").strip().upper()
        if not subject or not number:
            continue
        code = f"{subject} {number}"
        # A course can be offered more than once in a term (courseOfferNumber
        # 1, 2, ...). The course-level facts are identical across offerings and
        # the catalog is keyed on the code, so keep the first and skip the rest.
        if code in seen:
            continue
        seen.add(code)
        rows.append(
            CatalogRow(
                course_code=code,
                course_name=(c.get("title") or code)[:255],
                credits=STANDARD_UNITS,
                subject_faculty=subject,
                # `requirementsDescription` is prose that mixes prerequisites,
                # antirequisites and corequisites. The parser only ever emits
                # codes literally present in the text, so the failure mode is a
                # missing prerequisite (advice that is merely unhelpful) rather
                # than an invented one.
                prerequisites=parse_prerequisites(c.get("requirementsDescription")),
                gpa_gate=None,
            )
        )

    logger.info("Waterloo: fetched %d undergraduate courses for term %s", len(rows), term)
    return rows
