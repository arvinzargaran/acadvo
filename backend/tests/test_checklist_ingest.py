"""Guards on promoting a parsed degree checklist into the shared catalog.

The catalog is what every student at a university is advised against, so the bar
for entering it is higher than for one student's own rows. These tests pin the
boundary: carry across what the document says, drop anything half-read, and
never let one student's progress leak into shared data.
"""

from app.ingest.checklist import rows_from_parsed_document, source_label


def _doc(courses):
    return {"requirements": [], "courses": courses}


def test_carries_course_identity_across():
    rows = rows_from_parsed_document(
        _doc(
            [
                {
                    "course_code": "LE/EECS 2030",
                    "course_name": "Advanced Object Oriented Programming",
                    "credit_value": 3.0,
                    "prerequisites_raw": "Prerequisite: LE/EECS 1022.",
                }
            ]
        )
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["course_code"] == "LE/EECS 2030"
    assert row["course_name"] == "Advanced Object Oriented Programming"
    assert row["credits"] == 3.0
    assert row["subject_faculty"] == "EECS"
    assert row["prerequisites"] == [["LE/EECS 1022"]]


def test_rows_missing_code_or_name_are_dropped_not_guessed():
    rows = rows_from_parsed_document(
        _doc(
            [
                {"course_code": "", "course_name": "Nameless Orphan", "credit_value": 3.0},
                {"course_code": "LE/EECS 3101", "course_name": "", "credit_value": 3.0},
                {"course_code": "LE/EECS 2011", "course_name": "Fundamentals of Data Structures", "credit_value": 3.0},
            ]
        )
    )
    assert [r["course_code"] for r in rows] == ["LE/EECS 2011"]


def test_student_progress_never_enters_the_shared_catalog():
    """`status` and `grade` describe one person, not the course."""
    rows = rows_from_parsed_document(
        _doc(
            [
                {
                    "course_code": "LE/EECS 1019",
                    "course_name": "Discrete Mathematics for Computer Science",
                    "credit_value": 3.0,
                    "status": "completed",
                    "grade": "A+",
                }
            ]
        )
    )
    assert len(rows) == 1
    assert "status" not in rows[0]
    assert "grade" not in rows[0]


def test_duplicate_codes_collapse():
    rows = rows_from_parsed_document(
        _doc(
            [
                {"course_code": "LE/EECS 2011", "course_name": "Data Structures", "credit_value": 3.0},
                {"course_code": "LE/EECS2011", "course_name": "Data Structures (dupe)", "credit_value": 3.0},
            ]
        )
    )
    assert len(rows) == 1


def test_gpa_gate_is_carried_from_the_notes_column():
    rows = rows_from_parsed_document(
        _doc(
            [
                {
                    "course_code": "LE/EECS 3101",
                    "course_name": "Design and Analysis of Algorithms",
                    "credit_value": 3.0,
                    # The wording York's checklist actually uses.
                    "prerequisites_raw": "4.50 EECS GPA, LE/EECS 2011",
                }
            ]
        )
    )
    assert rows[0]["gpa_gate"] == {"scope": "EECS", "min": 4.5}


def test_empty_document_yields_nothing():
    assert rows_from_parsed_document(_doc([])) == []
    assert rows_from_parsed_document({}) == []


def test_source_label_records_provenance():
    assert source_label("york-bsc-hons-cs-2025-2026") == "checklist:york-bsc-hons-cs-2025-2026"


# ── Elective option lists ────────────────────────────────────────────

from app.ingest.checklist import extract_bucket_options

_YORK_LAB = (
    "Foundational Science Lab Credits (6.00): SC/BIOL 1000 3.00, SC/BIOL 1001 3.00, "
    "SC/CHEM 1000 3.00, SC/CHEM 1001 3.00, SC/PHYS 1011 3.00, SC/PHYS 1012 3.00, "
    "SC/PHYS 1411 3.00, SC/PHYS 1412 3.00, SC/PHYS 1421 3.00, SC/PHYS 1422 3.00"
)


def test_recovers_every_enumerated_option():
    """Verbatim from the real York BSc CS checklist."""
    opts = extract_bucket_options(_YORK_LAB)
    assert len(opts) == 10
    assert ("SC/BIOL 1000", 3.0) in opts
    assert ("SC/PHYS 1422", 3.0) in opts


def test_exclusion_list_is_never_read_as_options():
    """The inverse sentence must not become a menu — recommending these would
    push the student at courses the requirement explicitly rules out."""
    text = (
        _YORK_LAB
        + ". The following will not count towards this requirement: "
        "SC/BIOL 1500 3.00, SC/CHEM 1500 4.00, SC/PHYS 1510 4.00"
    )
    codes = {c for c, _ in extract_bucket_options(text)}
    assert "SC/BIOL 1000" in codes
    assert "SC/BIOL 1500" not in codes
    assert "SC/CHEM 1500" not in codes
    assert "SC/PHYS 1510" not in codes


def test_options_reach_the_catalog_rows():
    rows = rows_from_parsed_document(
        {
            "requirements": [
                {"bucket_name": "Foundational Science Lab", "description": _YORK_LAB}
            ],
            "courses": [],
        }
    )
    codes = {r["course_code"] for r in rows}
    assert len(codes) == 10
    assert all("Foundational Science Lab" in r["course_name"] for r in rows)


def test_a_named_course_keeps_its_real_name_over_the_bucket_label():
    rows = rows_from_parsed_document(
        {
            "requirements": [
                {"bucket_name": "Foundational Science Lab", "description": _YORK_LAB}
            ],
            "courses": [
                {
                    "course_code": "SC/BIOL 1000",
                    "course_name": "Biological Science",
                    "credit_value": 3.0,
                }
            ],
        }
    )
    biol = next(r for r in rows if r["course_code"] == "SC/BIOL 1000")
    assert biol["course_name"] == "Biological Science"


def test_prose_without_credits_yields_nothing():
    """Gen-ed points at a web page rather than listing courses; there is nothing
    to extract and we must not invent it."""
    assert extract_bucket_options(
        "Eligible Non-Science General Education Credits: Visit "
        "https://lassonde.yorku.ca/student-life/required-advising"
    ) == []
