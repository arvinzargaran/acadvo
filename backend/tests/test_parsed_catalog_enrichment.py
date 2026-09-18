"""A checklist names its required courses and leaves its options as bare codes.

York's real BSc Computer Science checklist writes elective buckets as option
lists — "Foundational Science Lab Credits (6.00): SC/BIOL 1000 3.00, SC/CHEM 1000
3.00, ..." — with a code and no title. That was 13 of 31 courses on the real
file: a third of the student's plan arriving as rows they cannot identify.

The catalog knows those titles, so the gaps are filled from it. What it must
never do is overwrite something the document actually said.
"""
from app.models.catalog import CatalogCourse
from app.services.catalog import enrich_parsed_with_catalog

YORK = "York University"


async def _seed(db):
    for code, name, credits in [
        ("SC/BIOL 1000", "Biology I - Cells, Molecular Biology and Genetics", 3.0),
        ("AP/ECON 1000", "Introduction to Microeconomics", 3.0),
        ("LE/EECS 1022", "Introduction to Object Oriented Programming", 3.0),
    ]:
        db.add(CatalogCourse(
            university=YORK, course_code=code, course_name=name, credits=credits,
            subject_faculty=code.split("/")[-1].split(" ")[0], prerequisites=[],
            gpa_gate=None, source="test",
        ))
    await db.commit()


async def test_blank_titles_are_filled_from_the_catalog(db):
    await _seed(db)
    parsed = {"courses": [
        {"course_code": "SC/BIOL 1000", "course_name": "", "credit_value": 3.0},
    ]}
    out = await enrich_parsed_with_catalog(parsed, YORK, db)
    assert out["courses"][0]["course_name"].startswith("Biology I")


async def test_a_bare_code_finds_its_prefixed_catalog_entry(db):
    """The checklist writes "ECON 1000"; the catalog holds "AP/ECON 1000". The
    prefix-tolerant lookup connects them, and the canonical code is adopted so
    the row matches everything downstream."""
    await _seed(db)
    parsed = {"courses": [{"course_code": "ECON 1000", "course_name": "", "credit_value": 3.0}]}
    out = await enrich_parsed_with_catalog(parsed, YORK, db)
    assert out["courses"][0]["course_code"] == "AP/ECON 1000"
    assert out["courses"][0]["course_name"] == "Introduction to Microeconomics"


async def test_a_title_the_document_stated_is_never_overwritten(db):
    """The document is the authority on the student's own program."""
    await _seed(db)
    parsed = {"courses": [
        {"course_code": "LE/EECS 1022", "course_name": "OOP (my own note)", "credit_value": 3.0},
    ]}
    out = await enrich_parsed_with_catalog(parsed, YORK, db)
    assert out["courses"][0]["course_name"] == "OOP (my own note)"


async def test_a_name_that_is_just_the_code_counts_as_missing(db):
    await _seed(db)
    parsed = {"courses": [
        {"course_code": "SC/BIOL 1000", "course_name": "SC/BIOL 1000", "credit_value": 3.0},
        {"course_code": "ECON 1000", "course_name": "ECON 1000", "credit_value": 3.0},
    ]}
    out = await enrich_parsed_with_catalog(parsed, YORK, db)
    assert out["courses"][0]["course_name"].startswith("Biology I")
    assert out["courses"][1]["course_name"] == "Introduction to Microeconomics"


async def test_missing_credits_are_filled_but_stated_ones_are_kept(db):
    await _seed(db)
    parsed = {"courses": [
        {"course_code": "SC/BIOL 1000", "course_name": "", "credit_value": 0},
        {"course_code": "AP/ECON 1000", "course_name": "", "credit_value": 6.0},
    ]}
    out = await enrich_parsed_with_catalog(parsed, YORK, db)
    assert out["courses"][0]["credit_value"] == 3.0
    assert out["courses"][1]["credit_value"] == 6.0


async def test_courses_absent_from_the_catalog_are_left_alone(db):
    """LW/LAW 3591 is on the real checklist and not in the undergraduate catalog.
    It keeps the code as its name rather than gaining an invented one."""
    await _seed(db)
    parsed = {"courses": [
        {"course_code": "LW/LAW 3591", "course_name": "LW/LAW 3591", "credit_value": 3.0},
    ]}
    out = await enrich_parsed_with_catalog(parsed, YORK, db)
    assert out["courses"][0]["course_name"] == "LW/LAW 3591"


async def test_no_university_and_no_catalog_are_both_no_ops(db):
    parsed = {"courses": [{"course_code": "SC/BIOL 1000", "course_name": "", "credit_value": 3.0}]}
    assert (await enrich_parsed_with_catalog(parsed, None, db))["courses"][0]["course_name"] == ""
    # University set, but nothing seeded for it.
    assert (await enrich_parsed_with_catalog(parsed, "Nowhere University", db))["courses"][0]["course_name"] == ""
