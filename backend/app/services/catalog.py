"""Course-catalog loader.

Merges the canonical, seeded catalog (``CatalogCourse``) for a university with a
student's own parsed ``Course`` rows as a fallback for codes that have not been
seeded, so downstream services always have a single lookup keyed by canonical
code.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func

from app.models.catalog import CatalogCourse
from app.models.degree import Course
from app.services.document_parser import normalize_course_code, subject_of


async def has_seeded_catalog(university: str | None, db: AsyncSession) -> bool:
    """True when a verified, seeded catalog (authoritative ``CatalogCourse`` rows)
    exists for ``university``. Callers use this to distinguish "verified" advising
    (grounded in a real catalog) from "best-effort" advising for universities we
    have not seeded yet — so the app can be honest about which one it is doing."""
    if not university:
        return False
    count = await db.scalar(
        select(func.count()).select_from(CatalogCourse).where(
            CatalogCourse.university == university
        )
    )
    return bool(count)


async def get_catalog_status(university: str | None, db: AsyncSession) -> dict:
    """Return a user-facing summary of the catalog backing advising for ``university``.

    The shape is::

        {
            "university": str | None,
            "verified": bool,          # True when >=1 seeded CatalogCourse row exists
            "course_count": int,       # number of CatalogCourse rows for the university
            "last_updated": datetime | None,  # max(updated_at) across those rows
            "sources": list[str],      # distinct `source` values, sorted
        }

    This lets the UI be honest about whether advising is grounded in a verified,
    seeded catalog or is running best-effort off the student's own uploads.
    """
    if not university:
        return {
            "university": None,
            "verified": False,
            "course_count": 0,
            "last_updated": None,
            "sources": [],
        }

    count = await db.scalar(
        select(func.count()).select_from(CatalogCourse).where(
            CatalogCourse.university == university
        )
    ) or 0

    last_updated = await db.scalar(
        select(func.max(CatalogCourse.updated_at)).where(
            CatalogCourse.university == university
        )
    )

    source_rows = await db.execute(
        select(CatalogCourse.source)
        .where(CatalogCourse.university == university)
        .distinct()
    )
    sources = sorted(s for s in source_rows.scalars() if s)

    subject_rows = await db.execute(
        select(CatalogCourse.subject_faculty)
        .where(CatalogCourse.university == university)
        .distinct()
    )
    subjects = sorted(s for s in subject_rows.scalars() if s)

    return {
        "university": university,
        "verified": count > 0,
        "course_count": count,
        "last_updated": last_updated,
        "sources": sources,
        # Which subject areas the catalog actually covers. A catalog is almost
        # never university-wide: it is built up one program document at a time,
        # so "we have a York catalog" can still mean "we have York's CS courses
        # and nothing a Psychology student needs". Callers must check coverage
        # against the student rather than treating `verified` as blanket truth.
        "subjects": subjects,
    }


class UniversityNotSetError(RuntimeError):
    """The student has not told us which university they attend.

    Everything catalog-grounded — recommendations, the semester plan, prereq and
    gate checks — is keyed on the university. Three call sites used to paper over
    a missing one with ``user.university or "York University"``, which is not a
    default so much as a wrong answer: a student who skipped that onboarding step
    was silently advised against York's catalog, in York's course-code format,
    under York's EECS GPA gate, with nothing on screen saying so. Asking is
    cheap; guessing produces advice that looks authoritative and is about
    somebody else's degree.
    """

    def __init__(self):
        super().__init__(
            "Set your university in your profile first — course advice is grounded "
            "in your university's own catalog, and Acadvo will not guess which one "
            "you attend."
        )


def require_university(user) -> str:
    """The user's university, or raise ``UniversityNotSetError``."""
    university = (getattr(user, "university", None) or "").strip()
    if not university:
        raise UniversityNotSetError()
    return university


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
