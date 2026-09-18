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


def strip_faculty(code: str) -> str:
    """``"HH/PSYC 1010"`` -> ``"PSYC 1010"``. Codes without a prefix are unchanged."""
    return code.split("/", 1)[1] if "/" in code else code


def strip_campus(code: str) -> str:
    """``"CPSC_V 100"`` -> ``"CPSC 100"``. Codes without a campus marker unchanged.

    UBC writes the campus into the subject. A student typing their own course
    almost always omits it, so the bare form has to find the marked one.
    """
    subject, _, rest = code.partition(" ")
    if "_" in subject:
        subject = subject.split("_", 1)[0]
        return f"{subject} {rest}" if rest else subject
    return code


def _bare_form(code: str) -> str:
    """The spelling a student is most likely to type: no faculty, no campus."""
    return strip_campus(strip_faculty(code))


def _campus_rank(code: str) -> int:
    """Ordering for resolving an ambiguous bare code. Lower wins."""
    subject = code.partition(" ")[0]
    if subject.endswith("_V"):
        return 0
    if subject.endswith("_O"):
        return 1
    return 2


class Catalog(dict):
    """A course catalog whose lookups tolerate a missing faculty prefix.

    York writes a faculty prefix into every course code (``HH/PSYC 1010``,
    ``AP/ECON 1000``, ``LE/EECS 2101``), and ``normalize_course_code`` can only
    restore a dropped one for the handful of subjects in ``FACULTY_PREFIXES`` —
    eight of them, all Science and Lassonde, because inventing a faculty for the
    hundreds of other York subjects would be fabricating data.

    So for every York student outside those eight subjects, the same course had
    two spellings: ``HH/PSYC 1010`` from their uploaded checklist and
    ``PSYC 1010`` from anywhere the prefix was absent. As two plain dict keys
    those are two different courses, and the consequences all landed on the
    student: their own course stored twice (counted twice toward the degree), a
    prerequisite never recognised as met, and — worst — a recommended course
    dropped as "fabricated" for not being in the catalog, which for a York
    Psychology student could silently empty an entire plan.

    Resolving this at the dict makes every existing call site correct without
    touching any of them: ``code in catalog`` and ``catalog.get(code)`` find the
    course whichever spelling they are handed. Iteration is unaffected — there are
    no duplicate keys, only a fallback index consulted on a miss.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bare_index: dict[str, str] | None = None
        self._indexed_len = -1

    def _resolve(self, key):
        if not isinstance(key, str) or "/" in key or "_" in key.partition(" ")[0]:
            # A key that already names a faculty or a campus and still missed is
            # genuinely absent. Two faculties are two different courses, and so
            # are two campuses — resolving CPSC_O 100 to Vancouver's CPSC_V 100
            # would hand an Okanagan student another campus's course.
            return None
        if self._bare_index is None or self._indexed_len != len(self):
            self._bare_index = {}
            for real in super().keys():
                bare = _bare_form(real)
                if bare == real:
                    continue
                existing = self._bare_index.get(bare)
                if existing is None:
                    self._bare_index[bare] = real
                elif _campus_rank(real) < _campus_rank(existing):
                    # Deterministic, not first-writer, because for UBC the
                    # ambiguity is real and common: 591 subject-and-number pairs
                    # exist at BOTH campuses as different courses. A bare code
                    # cannot say which, so it resolves to Vancouver — the larger
                    # campus and the likelier intent — every time, rather than to
                    # whichever row the database happened to return first.
                    self._bare_index[bare] = real
            self._indexed_len = len(self)
        return self._bare_index.get(key)

    def __contains__(self, key):
        if super().__contains__(key):
            return True
        return self._resolve(key) is not None

    def get(self, key, default=None):
        if super().__contains__(key):
            return super().__getitem__(key)
        real = self._resolve(key)
        return super().__getitem__(real) if real is not None else default

    def __getitem__(self, key):
        if super().__contains__(key):
            return super().__getitem__(key)
        real = self._resolve(key)
        if real is None:
            raise KeyError(key)
        return super().__getitem__(real)


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
    catalog: Catalog = Catalog()

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


async def enrich_parsed_with_catalog(
    parsed: dict, university: str | None, db: AsyncSession
) -> dict:
    """Fill in a parsed document's missing course names and credits from the
    seeded catalog, in place. Returns ``parsed``.

    A degree checklist names a course properly when it is a required one and
    leaves it as a bare code inside an options list ("Foundational Science Lab
    Credits (6.00): SC/BIOL 1000 3.00, SC/CHEM 1000 3.00, ..."). On the real York
    BSc Computer Science checklist that is 13 of 31 courses — a third of the
    student's plan arriving as rows with no title.

    The catalog knows those titles: ``SC/BIOL 1000`` is "Biology I - Cells,
    Molecular Biology and Genetics". Since the lookup is prefix-tolerant, the
    checklist's bare ``ECON 1000`` finds the catalog's ``AP/ECON 1000`` too, and
    the canonical code replaces the bare one so the row matches everything
    downstream.

    Only ever fills gaps: a title the document actually stated is left alone,
    because the document is the authority on the student's own program and the
    catalog is only the authority on what a course is called.
    """
    if not university:
        return parsed

    catalog = await get_catalog(university, db)
    if not catalog:
        return parsed

    for course in parsed.get("courses") or []:
        raw_code = course.get("course_code") or ""
        code = normalize_course_code(raw_code)
        entry = catalog.get(code)
        if entry is None:
            continue
        name = (course.get("course_name") or "").strip()
        # A name equal to the code is the parser's own placeholder, not a title.
        if not name or name.replace(" ", "") == code.replace(" ", "") or (
            name.replace(" ", "") == strip_faculty(code).replace(" ", "")
        ):
            course["course_name"] = entry["course_name"]
        try:
            credits = float(course.get("credit_value") or 0)
        except (TypeError, ValueError):
            credits = 0.0
        if credits <= 0:
            course["credit_value"] = float(entry["credits"])
        # Adopt the catalog's canonical code (restores a dropped faculty prefix).
        course["course_code"] = entry.get("course_code", code)

    return parsed
