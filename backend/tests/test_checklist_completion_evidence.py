"""Completion must follow the document's evidence — in either direction.

Two failures pull against each other here, and both have actually happened:

  * A blank York checklist came back with a whole first year marked "completed"
    because the student's start year made it plausible. That fabricates an
    academic record.
  * The guard added to stop that accepted a GRADE as the only evidence. York's
    own BSc Computer Science checklist has no grade column at all — it records
    Enrolled/Passed booleans — so on the real 2025-2026 file every course the
    student had passed was downgraded to "planned", and the app reported zero
    credits completed for someone most of the way through first year.

The rule that satisfies both: completion needs evidence quoted from the
document, and a grade is only one kind.
"""
from app.services.document_parser import _postprocess


def _doc(courses):
    return {"requirements": [], "courses": courses}


def _course(**over):
    base = {
        "course_code": "LE/EECS 1022",
        "course_name": "Introduction to Object Oriented Programming",
        "credit_value": 3.0,
        "requirement_bucket": "EECS Major Core",
        "status": "not_scheduled",
        "grade": None,
        "completion_evidence": None,
        "prerequisites_raw": "",
        "alternatives": [],
    }
    base.update(over)
    return base


def test_passed_column_counts_as_completion_without_a_grade():
    """The real York checklist case: no grade column anywhere, progress recorded
    as Enrolled/Passed booleans."""
    out = _postprocess(_doc([
        _course(status="completed", completion_evidence="Passed: True"),
    ]))
    course = out["courses"][0]
    assert course["status"] == "completed"
    assert course["completion_evidence"] == "Passed: True"


def test_grade_still_counts_on_its_own():
    out = _postprocess(_doc([_course(status="completed", grade="B+")]))
    assert out["courses"][0]["status"] == "completed"


def test_completed_with_no_evidence_is_downgraded():
    """The original fabrication guard. A blank checklist offers neither a grade
    nor a quotable mark, so nothing may be claimed as done."""
    out = _postprocess(_doc([_course(status="completed")]))
    assert out["courses"][0]["status"] == "planned"


def test_blank_evidence_string_is_not_evidence():
    out = _postprocess(_doc([_course(status="completed", completion_evidence="   ")]))
    assert out["courses"][0]["status"] == "planned"
    assert out["courses"][0]["completion_evidence"] is None


def test_evidence_is_cleared_on_courses_that_are_not_completed():
    """Evidence means something only on a completed course; leaving it on a
    planned one invites a later reader to treat it as a claim."""
    out = _postprocess(_doc([
        _course(status="in_progress", completion_evidence="Passed: True"),
    ]))
    assert out["courses"][0]["completion_evidence"] is None


def test_the_real_checklist_mix_survives():
    """A row-for-row slice of the real file: passed, enrolled-not-passed, blank."""
    out = _postprocess(_doc([
        _course(course_code="LE/EECS 1001", status="completed",
                completion_evidence="Enrolled: True, Passed: True"),
        _course(course_code="LE/EECS 2001", status="in_progress"),
        _course(course_code="LE/EECS 4101", status="not_scheduled"),
    ]))
    by_code = {c["course_code"]: c["status"] for c in out["courses"]}
    assert by_code == {
        "LE/EECS 1001": "completed",
        "LE/EECS 2001": "in_progress",
        "LE/EECS 4101": "not_scheduled",
    }
