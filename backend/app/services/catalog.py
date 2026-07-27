"""Course-catalog loader.

Merges the canonical, seeded catalog (``CatalogCourse``) for a university with a
student's own parsed ``Course`` rows as a fallback for codes that have not been
seeded, so downstream services always have a single lookup keyed by canonical
code.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CatalogCourse
from app.models.degree import Course
from app.services.document_parser import normalize_course_code, subject_of


async def get_catalog(
    university: str,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> dict[str, dict]:
    """Return the merged course catalog for ``university``, keyed by canonical code.

    The returned mapping is ``{canonical_code: entry}`` where each ``entry`` is::

        {
            "course_code": str,        # canonical, e.g. "LE/EECS 2101"
            "course_name": str,        # canonical name
            "credits": float,
            "subject_faculty": str | None,  # e.g. "EECS", "MATH"
            "prerequisites": list[list[str]],  # groups of alternative codes
                                               # (AND across groups, OR within)
            "gpa_gate": dict | None,   # e.g. {"scope": "EECS", "min": 4.5}
            "source": str,             # "catalog" (seeded) or "student" (fallback)
        }

    This lets callers:
      (a) check a code exists          -> ``code in catalog``
      (b) look up canonical name/credits -> ``catalog[code]["course_name" / "credits"]``
      (c) read prereqs & gpa_gate       -> ``catalog[code]["prerequisites" / "gpa_gate"]``

    Seeded ``CatalogCourse`` rows are authoritative (source ``"catalog"``). When
    ``user_id`` is provided, the student's ``Course`` rows fill in any codes not
    present in the seeded catalog (source ``"student"``, empty prereqs/gate).
    """
    catalog: dict[str, dict] = {}

    # Canonical/primary layer: seeded catalog rows.
    result = await db.execute(
        select(CatalogCourse).where(CatalogCourse.university == university)
    )
    for row in result.scalars():
        code = normalize_course_code(row.course_code)
        catalog[code] = {
            "course_code": code,
            "course_name": row.course_name,
            "credits": float(row.credits),
            "subject_faculty": row.subject_faculty,
            "prerequisites": row.prerequisites or [],
            "gpa_gate": row.gpa_gate,
            "source": "catalog",
        }

    # Fallback layer: the student's own courses for codes not yet seeded.
    if user_id is not None:
        result = await db.execute(select(Course).where(Course.user_id == user_id))
        for course in result.scalars():
            code = normalize_course_code(course.course_code)
            if not code or code in catalog:
                continue
            catalog[code] = {
                "course_code": code,
                "course_name": course.course_name,
                "credits": float(course.credit_value),
                "subject_faculty": subject_of(code),
                "prerequisites": [],
                "gpa_gate": None,
                "source": "student",
            }

    return catalog
