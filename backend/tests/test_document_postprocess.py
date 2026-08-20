"""Deterministic clean-up of whatever the model returns from a degree document.

`_postprocess` is the layer between a language model and a student's academic
record. It is pure, deterministic and idempotent — and it was completely
untested, despite carrying the single most consequential guard in the app.

That guard has a history. A blank York checklist once came back with a whole
first year marked "completed" purely because the student's start year made it
plausible, fabricating an academic record that every downstream number — GPA,
credits earned, requirements remaining, graduation date — was then computed from.
The prompt forbids inferring completion; prompts drift, so the code enforces it.
"""
from app.services.document_parser import _postprocess


def _doc(courses=None, requirements=None):
    return {"courses": courses or [], "requirements": requirements or []}


# ── Completion needs evidence ────────────────────────────────────────


def test_completed_without_a_grade_is_downgraded_to_planned():
    out = _postprocess(_doc([
        {"course_code": "EECS 1012", "course_name": "Intro", "credit_value": 3, "status": "completed"},
    ]))
    assert out["courses"][0]["status"] == "planned"


def test_completed_with_a_grade_is_believed():
    out = _postprocess(_doc([
        {"course_code": "EECS 1012", "course_name": "Intro", "credit_value": 3,
         "status": "completed", "grade": "B+"},
    ]))
    assert out["courses"][0]["status"] == "completed"


def test_a_whitespace_grade_is_not_evidence():
    out = _postprocess(_doc([
        {"course_code": "EECS 1012", "course_name": "Intro", "credit_value": 3,
         "status": "completed", "grade": "   "},
    ]))
    assert out["courses"][0]["status"] == "planned"


def test_the_guard_does_not_touch_other_statuses():
    """in_progress legitimately has no grade yet — downgrading it would erase
    the courses the student is sitting in right now."""
    out = _postprocess(_doc([
        {"course_code": "EECS 2030", "course_name": "OOP", "credit_value": 3, "status": "in_progress"},
    ]))
    assert out["courses"][0]["status"] == "in_progress"


# ── Status vocabulary ────────────────────────────────────────────────


def test_synonyms_map_onto_the_four_real_statuses():
    rows = [
        ("enrolled", "in_progress"),
        ("registered", "in_progress"),
        ("taking", "in_progress"),
        ("withdrawn", "not_scheduled"),
        ("dropped", "not_scheduled"),
        ("not completed", "planned"),
    ]
    out = _postprocess(_doc([
        {"course_code": f"X {i}", "course_name": "n", "credit_value": 3, "status": raw}
        for i, (raw, _) in enumerate(rows)
    ]))
    assert [c["status"] for c in out["courses"]] == [want for _, want in rows]


def test_a_failed_course_is_completed_only_with_a_grade():
    """"Failed" is a completion — it consumed a term and it affects GPA — but it
    still goes through the evidence guard like any other."""
    graded = _postprocess(_doc([
        {"course_code": "X 1", "course_name": "n", "credit_value": 3, "status": "failed", "grade": "F"},
    ]))
    assert graded["courses"][0]["status"] == "completed"

    ungraded = _postprocess(_doc([
        {"course_code": "X 2", "course_name": "n", "credit_value": 3, "status": "failed"},
    ]))
    assert ungraded["courses"][0]["status"] == "planned"


def test_an_unrecognised_status_becomes_planned_not_completed():
    """The safe direction. Anything unknown must never land on 'completed'."""
    out = _postprocess(_doc([
        {"course_code": "X 1", "course_name": "n", "credit_value": 3, "status": "¯\\_(ツ)_/¯"},
    ]))
    assert out["courses"][0]["status"] == "planned"


# ── Coercion of model-supplied numbers ───────────────────────────────


def test_non_numeric_credits_become_zero_rather_than_raising():
    out = _postprocess(_doc(
        [{"course_code": "X 1", "course_name": "n", "credit_value": "three"}],
        [{"bucket_name": "Core", "credits_required": "lots"}],
    ))
    assert out["courses"][0]["credit_value"] == 0.0
    assert out["requirements"][0]["credits_required"] == 0.0


def test_missing_fields_are_filled_not_dropped():
    out = _postprocess(_doc([{"status": "planned"}]))
    course = out["courses"][0]
    assert course["course_code"] == ""
    assert course["course_name"] == ""
    assert course["credit_value"] == 0.0


# ── Degree total ─────────────────────────────────────────────────────


def test_a_degree_total_bucket_is_always_present():
    """The degree summary reads this bucket for its overall denominator; without
    one, progress is a percentage of nothing."""
    out = _postprocess(_doc(requirements=[{"bucket_name": "Major", "credits_required": 42}]))
    names = [r["bucket_name"] for r in out["requirements"]]
    assert any("Degree Total" in n for n in names)


def test_an_existing_total_is_respected_not_duplicated():
    out = _postprocess(_doc(requirements=[
        {"bucket_name": "Program Total Credits", "credits_required": 90},
    ]))
    totals = [r for r in out["requirements"] if "total" in r["bucket_name"].lower()]
    assert len(totals) == 1
    assert totals[0]["credits_required"] == 90


def test_a_total_bucket_with_no_number_gets_the_default():
    out = _postprocess(_doc(requirements=[
        {"bucket_name": "Degree Total Credits", "credits_required": 0},
    ]))
    totals = [r for r in out["requirements"] if "total" in r["bucket_name"].lower()]
    assert totals[0]["credits_required"] == 120.0


# ── Idempotence ──────────────────────────────────────────────────────


def test_running_twice_changes_nothing():
    """Documented as idempotent, and the ingestion CLI relies on it: a parsed
    file can be reviewed, re-read and promoted without drifting."""
    doc = _doc(
        [{"course_code": "EECS 1012", "course_name": "Intro", "credit_value": 3,
          "status": "completed", "grade": "A"}],
        [{"bucket_name": "Major", "credits_required": 42}],
    )
    once = _postprocess(doc)
    twice = _postprocess(once)
    assert once == twice
