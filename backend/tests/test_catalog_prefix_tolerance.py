"""A York course must be findable whether or not its faculty prefix survived.

York writes a faculty into every code (``HH/PSYC 1010``), and the normalizer can
only restore a dropped prefix for the eight Science/Lassonde subjects it knows —
inventing a faculty for York's hundreds of other subjects would be fabricating
data. That left every non-CS York student with two spellings of the same course
and no connection between them.
"""
from app.models.catalog import CatalogCourse
from app.models.degree import Course, CourseStatus
from app.services.catalog import Catalog, get_catalog, strip_faculty


def test_lookup_finds_a_prefixed_course_from_its_bare_code():
    catalog = Catalog({"HH/PSYC 1010": {"course_name": "Introduction to Psychology"}})
    assert "PSYC 1010" in catalog
    assert catalog.get("PSYC 1010")["course_name"] == "Introduction to Psychology"
    assert catalog["PSYC 1010"] is catalog["HH/PSYC 1010"]


def test_a_different_faculty_is_still_a_different_course():
    """Tolerance runs one way only. A code that names a faculty means that
    faculty's course, and quietly resolving it to another one would be a wrong
    answer rather than a missing one."""
    catalog = Catalog({"HH/PSYC 1010": {"course_name": "Introduction to Psychology"}})
    assert "AP/PSYC 1010" not in catalog
    assert catalog.get("AP/PSYC 1010") is None


def test_absent_courses_still_miss():
    catalog = Catalog({"HH/PSYC 1010": {}})
    assert "BIOL 9999" not in catalog
    assert catalog.get("BIOL 9999") is None
    try:
        catalog["BIOL 9999"]
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError")


def test_iteration_is_not_polluted_by_the_alias_index():
    """The fallback is an index, not extra rows: prompts and shortlists built by
    iterating the catalog must not see each course twice."""
    catalog = Catalog({"HH/PSYC 1010": {}, "LE/EECS 2101": {}})
    assert catalog.get("PSYC 1010") is not None       # index is now built
    assert list(catalog) == ["HH/PSYC 1010", "LE/EECS 2101"]
    assert len(catalog) == 2


def test_index_refreshes_when_the_catalog_grows():
    catalog = Catalog({"HH/PSYC 1010": {}})
    assert "PSYC 1010" in catalog
    catalog["AP/ECON 1000"] = {}
    assert "ECON 1000" in catalog


def test_strip_faculty():
    assert strip_faculty("HH/PSYC 1010") == "PSYC 1010"
    assert strip_faculty("CS 245") == "CS 245"


async def test_students_own_course_is_not_stored_twice(db, test_user):
    """The concrete harm: the seeded catalog has HH/PSYC 1010 and the student's
    upload has the bare form, so the student layer added a SECOND entry for a
    course they are already credited with."""
    db.add(CatalogCourse(
        university="York University", course_code="HH/PSYC 1010",
        course_name="Introduction to Psychology", credits=6.0,
        subject_faculty="PSYC", prerequisites=[], gpa_gate=None, source="checklist:test",
    ))
    db.add(Course(
        user_id=test_user.id, course_code="PSYC 1010", course_name="Intro Psych",
        credit_value=6.0, status=CourseStatus.completed,
    ))
    await db.commit()

    catalog = await get_catalog("York University", db, test_user.id)
    psyc = [c for c in catalog if c.endswith("PSYC 1010")]
    assert psyc == ["HH/PSYC 1010"], f"course stored twice: {psyc}"
    # And it resolves to the authoritative seeded row, not the student's copy.
    assert catalog["PSYC 1010"]["source"] == "catalog"
    assert catalog["PSYC 1010"]["course_name"] == "Introduction to Psychology"
