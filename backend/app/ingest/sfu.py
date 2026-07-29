"""Adapter for Simon Fraser University's public course-outlines API.

SFU exposes a keyless, official JSON API that walks:
    terms         GET ?{year}/{term}                       -> departments
    departments   GET ?{year}/{term}/{dept}                -> course numbers
    numbers       GET ?{year}/{term}/{dept}/{number}       -> sections
    section       GET ?{year}/{term}/{dept}/{number}/{sec} -> full course info
                  (title, units, prerequisites, description, ...)

Course-level facts (name, units, prerequisites) are identical across a course's
sections, so we read just the first section per course. Prerequisite prose is
parsed into the app's structured form via ``prereq_parser``.

Docs: https://www.sfu.ca/outlines/help/api.html
"""
from __future__ import annotations

import logging
import time

import httpx

from app.ingest.prereq_parser import parse_prerequisites
from app.ingest.store import CatalogRow

logger = logging.getLogger("acadvo.ingest.sfu")

UNIVERSITY = "Simon Fraser University"
SOURCE = "sfu_course_outlines"
_BASE = "https://www.sfu.ca/bin/wcm/course-outlines"


def _units_to_credits(units: str | None) -> float:
    """Parse SFU's ``units`` string ("3", "0", "3-4") into a credit float."""
    if not units:
        return 3.0
    num = ""
    for ch in str(units):
        if ch.isdigit() or ch == ".":
            num += ch
        elif num:
            break
    try:
        return float(num) if num else 3.0
    except ValueError:
        return 3.0


def _get(client: httpx.Client, path: str, throttle: float) -> list | dict | None:
    """GET ``?{path}`` and return parsed JSON, or None on any error (best-effort;
    one course failing must not abort the whole ingest)."""
    try:
        # SFU expects the whole descriptor as a raw query string (e.g. "?2024/fall"),
        # not key=value params — build the URL directly so the slashes survive.
        resp = client.get(f"{_BASE}?{path}", timeout=20.0)
        if throttle:
            time.sleep(throttle)
        if resp.status_code != 200:
            return None
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("SFU fetch failed for %s: %s", path, exc)
        return None


def fetch_courses(
    term: str,
    departments: list[str] | None = None,
    *,
    throttle: float = 0.15,
) -> list[CatalogRow]:
    """Walk the SFU API for ``term`` (e.g. "2024/fall") and return catalog rows.

    ``departments`` (lowercase codes like ["cmpt", "macm"]) restricts the crawl;
    ``None`` ingests every department in the term. ``throttle`` is the polite
    delay between requests (seconds)."""
    rows: list[CatalogRow] = []
    with httpx.Client(headers={"User-Agent": "acadvo-catalog-ingest"}) as client:
        dept_list = _get(client, term, throttle) or []
        wanted = {d.lower() for d in departments} if departments else None
        for dept in dept_list:
            dcode = dept.get("value")
            if not dcode or (wanted is not None and dcode.lower() not in wanted):
                continue
            numbers = _get(client, f"{term}/{dcode}", throttle) or []
            for num in numbers:
                ncode = num.get("value")
                if not ncode:
                    continue
                sections = _get(client, f"{term}/{dcode}/{ncode}", throttle) or []
                if not sections:
                    continue
                sec = sections[0].get("value")
                if not sec:
                    continue
                detail = _get(client, f"{term}/{dcode}/{ncode}/{sec}", throttle)
                info = (detail or {}).get("info", {}) if isinstance(detail, dict) else {}
                if not info:
                    continue
                dept_code = (info.get("dept") or dcode).upper()
                number = (info.get("number") or ncode).upper()
                code = f"{dept_code} {number}"
                name = info.get("title") or num.get("title") or code
                rows.append(
                    CatalogRow(
                        course_code=code,
                        course_name=name[:255],
                        credits=_units_to_credits(info.get("units")),
                        subject_faculty=dept_code,
                        prerequisites=parse_prerequisites(info.get("prerequisites")),
                        gpa_gate=None,
                    )
                )
    logger.info("SFU: fetched %d courses for %s", len(rows), term)
    return rows
