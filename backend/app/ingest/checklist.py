"""Adapter: promote an official degree checklist / calendar extract into the
shared catalog.

Why this exists
---------------
Most universities do not publish a machine-readable course API. Of the schools
Acadvo lists, exactly one (SFU) does. The others either have no public API, or
put their course system behind bot protection — and defeating that is not on the
table (see ``SOURCES.md``).

But the authoritative document *is* public, and students already hold it: the
official degree checklist. Acadvo can already read one — that is what
``services/document_parser`` does, and it is the same artifact a student uploads
during onboarding.

The only thing missing was that a parse landed in one student's ``Course`` rows
and helped nobody else. This adapter takes the same parsed output and writes it
to ``CatalogCourse``, so it becomes the verified catalog every student at that
university is advised against.

That makes the catalog problem a *document* problem rather than a scraping
problem, and it works for any school that publishes a checklist.

What this is NOT
----------------
This does not invent courses. It carries across exactly what the document says.
A course the document does not contain does not enter the catalog. Two guards
enforce the boundary:

  * ``course_code`` and ``course_name`` must both be present, or the row is
    dropped — a half-parsed line is not a course.
  * Student progress is discarded entirely. ``status`` and ``grade`` describe
    one person's record and have no place in a shared catalog; only the course's
    own identity (code, name, credits, prerequisites, GPA gate) crosses over.

Provenance is recorded as ``source="checklist:<label>"`` so
``get_catalog_status`` can tell a student where their advising is grounded, and
so a later authoritative import can be told apart from this one.
"""
from __future__ import annotations

import logging
import re

from app.ingest.store import CatalogRow
from app.services.document_parser import (
    normalize_course_code,
    parse_gpa_gate,
    parse_prerequisites_from_notes,
    subject_of,
)

logger = logging.getLogger("acadvo.ingest.checklist")

SOURCE_PREFIX = "checklist"


def source_label(label: str) -> str:
    """Provenance tag for rows ingested from a named document."""
    return f"{SOURCE_PREFIX}:{label}"


# "SC/BIOL 1000 3.00" — a code immediately followed by its credit value.
_CODE_CREDITS_RE = re.compile(
    r"\b((?:[A-Z]{2}/)?[A-Z]{2,5}\s?\d{4})\s+(\d+\.\d{2})\b"
)

# The sentence that flips a list from "these count" to "these do not".
_EXCLUSION_RE = re.compile(
    r"(will not count|do(?:es)? not count|not count towards|excluded from)",
    re.IGNORECASE,
)


def extract_bucket_options(text: str | None) -> list[tuple[str, float]]:
    """Pull the enumerated course options out of a requirement's description.

    A degree checklist does not only list the courses a student must take; for
    some requirements it spells out which courses *satisfy* them::

        Foundational Science Lab Credits (6.00): SC/BIOL 1000 3.00,
        SC/BIOL 1001 3.00, SC/CHEM 1000 3.00, ...

    Those ten courses are real, they are in the document, and the ordinary
    course-row parse throws them away — it emits one entry named after the
    bucket. Recovering them is the difference between an advisor that can answer
    "which science lab should I take?" and one that cannot.

    **Exclusion lists are honoured.** The same documents carry the inverse::

        The following will not count towards this requirement:
        SC/BIOL 1500 3.00, SC/CHEM 1500 4.00, SC/PHYS 1510 4.00

    Reading that as a list of options would have the advisor recommend exactly
    the courses the requirement rules out. Any codes appearing after an
    exclusion phrase are dropped.

    Returns ``[(canonical_code, credits), ...]``, de-duplicated, order preserved.
    """
    if not text:
        return []

    # Everything from the first exclusion phrase onward is a denylist, not a
    # menu. Split there and keep only what precedes it.
    match = _EXCLUSION_RE.search(text)
    allowed_region = text[: match.start()] if match else text

    out: list[tuple[str, float]] = []
    seen: set[str] = set()
    for raw_code, raw_credits in _CODE_CREDITS_RE.findall(allowed_region):
        code = normalize_course_code(raw_code)
        if not code or code in seen:
            continue
        try:
            credits = float(raw_credits)
        except ValueError:
            continue
        seen.add(code)
        out.append((code, credits))
    return out


def rows_from_parsed_document(
    parsed: dict, university: str | None = None
) -> list[CatalogRow]:
    """Convert ``document_parser`` output into catalog rows.

    ``parsed`` is the shape ``parse_document`` returns: ``{"requirements": [...],
    "courses": [{course_code, course_name, credit_value, prerequisites_raw, ...}]}``.

    ``university`` sets what a course is worth when the document does not say.
    This is the ingestion path for every school with no API — TMU and UofT among
    them — and it used to fall back to York's 3.0 credits, writing 3.0 for a UofT
    half-course worth 0.5 and for a TMU course worth 1.00. The fallback now comes
    from the school's own credit model, derived from the credit values elsewhere
    in the same document wherever the parse supplied any.
    """
    from app.data.credit_models import get_credit_model

    parsed_courses = parsed.get("courses") or []
    default_credits = get_credit_model(
        university,
        student_credit_values=[c.get("credit_value") for c in parsed_courses],
    ).unit
    rows: list[CatalogRow] = []
    seen: set[str] = set()
    skipped = 0

    for course in parsed.get("courses") or []:
        code = normalize_course_code(course.get("course_code"))
        name = (course.get("course_name") or "").strip()

        # A course needs both an identity and a name. Anything less is a parse
        # artifact, and guessing the missing half is exactly the fabrication
        # this pipeline exists to prevent.
        if not code or not name:
            skipped += 1
            continue
        if code in seen:
            continue
        seen.add(code)

        try:
            credits = float(course.get("credit_value") or 0) or default_credits
        except (TypeError, ValueError):
            credits = default_credits

        notes = course.get("prerequisites_raw") or ""
        # Prefer prerequisites the parser already structured; fall back to
        # re-reading the raw notes column.
        prereqs = course.get("prerequisites") or parse_prerequisites_from_notes(notes)

        rows.append(
            CatalogRow(
                course_code=code,
                course_name=name[:255],
                credits=credits,
                subject_faculty=subject_of(code),
                prerequisites=prereqs or [],
                gpa_gate=parse_gpa_gate(notes),
            )
        )

    # Second pass: recover the courses that only appear inside a requirement's
    # option list. Named after the bucket they satisfy, because that is the only
    # name the document gives them — flagged so review can see what needs a
    # proper title. Existing rows win; a course spelled out in full earlier
    # keeps its real name.
    for req in parsed.get("requirements") or []:
        bucket = (req.get("bucket_name") or "").strip()
        for source_text in (
            req.get("options_raw"),
            req.get("description"),
            req.get("notes"),
            bucket,
        ):
            for code, credits in extract_bucket_options(source_text):
                if code in seen:
                    continue
                seen.add(code)
                rows.append(
                    CatalogRow(
                        course_code=code,
                        course_name=f"{bucket} option" if bucket else code,
                        credits=credits,
                        subject_faculty=subject_of(code),
                        prerequisites=[],
                        gpa_gate=None,
                    )
                )

    if skipped:
        logger.warning(
            "checklist: skipped %d row(s) missing a course code or name", skipped
        )
    logger.info("checklist: prepared %d catalog rows", len(rows))
    return rows
