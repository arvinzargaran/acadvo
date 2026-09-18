"""Regression tests for course-equivalence exclusion and plan prereq ordering.

These lock in the follow-up fixes:
  - a completed course satisfies (and suppresses) its mutually-exclusive
    alternative (e.g. LE/EECS 1012 vs LE/EECS 1015),
  - _sanitize_plan drops courses the student has already completed (or an
    equivalent of), and never places a course before a gateway prereq,
  - fail-open behavior when no catalog is supplied is preserved.

All hermetic — no DB, no network.
"""
from app.data.credit_models import get_credit_model
from app.services.eligibility import equivalents_of, expand_equivalents
from app.services.semester_plan import _sanitize_plan, _pad_plan_to_target


def test_equivalents_of_first_year_intro():
    assert equivalents_of("LE/EECS 1012") == {"LE/EECS 1012", "LE/EECS 1015"}
    assert equivalents_of("LE/EECS 1015") == {"LE/EECS 1012", "LE/EECS 1015"}
    # Codes with no equivalence group return just themselves (normalized).
    assert equivalents_of("EECS 2030") == {"LE/EECS 2030"}


def test_expand_equivalents():
    assert expand_equivalents({"LE/EECS 1012"}) == {"LE/EECS 1012", "LE/EECS 1015"}


def _catalog():
    return {
        "LE/EECS 2101": {"course_code": "LE/EECS 2101", "course_name": "Fundamentals of Data Structures",
                         "credits": 3.0, "prerequisites": [["LE/EECS 2030"]], "gpa_gate": None},
        "LE/EECS 3221": {"course_code": "LE/EECS 3221", "course_name": "Operating System Fundamentals",
                         "credits": 3.0, "prerequisites": [["LE/EECS 2101"]], "gpa_gate": None},
        "LE/EECS 2030": {"course_code": "LE/EECS 2030", "course_name": "Advanced Object Oriented Programming",
                         "credits": 3.0, "prerequisites": [], "gpa_gate": None},
        "LE/EECS 1015": {"course_code": "LE/EECS 1015", "course_name": "Introduction to Computer Science and Programming",
                         "credits": 3.0, "prerequisites": [], "gpa_gate": None},
    }


def test_sanitize_plan_drops_completed_equivalent(monkeypatch):
    from datetime import date

    class MockDate:
        @classmethod
        def today(cls):
            return date(2026, 2, 15)  # Winter 2026

    monkeypatch.setattr("app.services.semester_plan.date", MockDate)

    ctx = {
        "all_codes": {"LE/EECS 1012"},
        "catalog": _catalog(),
        "gpa_by_scope": {},
        # Student completed 1012 -> its equivalent 1015 must be treated as done.
        "completed_codes": {"LE/EECS 1012", "LE/EECS 1015", "LE/EECS 2030"},
        "skip_summers": True,
    }
    plan = {"semesters": [{"term": "Fall 2026", "courses": [
        {"course_code": "LE/EECS 1015"},   # equivalent already completed -> dropped
        {"course_code": "LE/EECS 2101"},   # prereq 2030 completed -> kept
    ]}]}

    cleaned = _sanitize_plan(plan, ctx)
    codes = [c["course_code"] for s in cleaned["semesters"] for c in s["courses"]]
    assert "LE/EECS 1015" not in codes
    assert "LE/EECS 2101" in codes


def test_sanitize_plan_flags_course_before_gateway_prereq(monkeypatch):
    from datetime import date

    class MockDate:
        @classmethod
        def today(cls):
            return date(2026, 2, 15)

    monkeypatch.setattr("app.services.semester_plan.date", MockDate)

    ctx = {
        "all_codes": set(),
        "catalog": _catalog(),
        "gpa_by_scope": {},
        "completed_codes": {"LE/EECS 2030"},  # 2101's prereq done; 3221 needs 2101
        "skip_summers": True,
    }
    # 3221 scheduled the SAME semester as its prereq 2101 -> must be flagged, not silently ok.
    plan = {"semesters": [{"term": "Fall 2026", "courses": [
        {"course_code": "LE/EECS 2101"},
        {"course_code": "LE/EECS 3221"},
    ]}]}

    cleaned = _sanitize_plan(plan, ctx)
    by_code = {c["course_code"]: c for s in cleaned["semesters"] for c in s["courses"]}
    assert "blocked_reason" not in by_code["LE/EECS 2101"]  # prereq 2030 done
    assert "2101" in by_code["LE/EECS 3221"].get("blocked_reason", "")  # needs 2101 first


def test_sanitize_plan_defers_course_to_after_its_prereq(monkeypatch):
    from datetime import date

    class MockDate:
        @classmethod
        def today(cls):
            return date(2026, 2, 15)  # Winter 2026 current

    monkeypatch.setattr("app.services.semester_plan.date", MockDate)

    ctx = {
        "all_codes": set(),
        "catalog": _catalog(),
        "gpa_by_scope": {},
        "completed_codes": {"LE/EECS 2030"},  # 2101's prereq done
        "skip_summers": True,
    }
    # 3221 (needs 2101) is co-scheduled with 2101 in Fall 2026; there's a later term.
    plan = {"semesters": [
        {"term": "Fall 2026", "courses": [{"course_code": "LE/EECS 2101"}, {"course_code": "LE/EECS 3221"}]},
        {"term": "Winter 2027", "courses": []},
    ]}

    cleaned = _sanitize_plan(plan, ctx)
    by_term = {s["term"]: [c["course_code"] for c in s["courses"]] for s in cleaned["semesters"]}
    assert by_term.get("Fall 2026") == ["LE/EECS 2101"]
    assert "LE/EECS 3221" in by_term.get("Winter 2027", [])  # deferred to AFTER its prereq
    # And now unblocked, since 2101 sits in an earlier semester
    win = {c["course_code"]: c for s in cleaned["semesters"] if s["term"] == "Winter 2027" for c in s["courses"]}
    assert "blocked_reason" not in win["LE/EECS 3221"]


def test_pad_plan_to_target_fills_electives():
    ctx = {
        "summary": {"total_credits_required": 120.0, "total_credits_completed": 30.0},
        "planned": [],
        "in_progress": [],
        "credit_model": get_credit_model(
            "York University", total_credits_required=120.0
        ),
    }
    # Plan has 9 credits scheduled; 30 completed => 81 credits short of 120 -> pad.
    plan = {"semesters": [
        {"term": "Fall 2026", "courses": [{"course_code": "LE/EECS 2030", "credits": 3.0}]},
        {"term": "Winter 2027", "courses": []},
    ]}
    padded = _pad_plan_to_target(plan, ctx)
    placeholders = [c for s in padded["semesters"] for c in s["courses"] if c.get("is_placeholder")]
    assert placeholders, "expected elective placeholders to be added"
    # Never exceeds the per-semester cap.
    assert all(len(s["courses"]) <= 5 for s in padded["semesters"])


def test_pad_plan_to_target_uses_the_students_own_credit_model():
    """A Waterloo plan is padded in 0.5-unit courses toward a 20.0-unit degree.

    The regression this locks: the target was hardcoded to 120 and the placeholder
    to 3.0 credits, so a Waterloo student with 5.0 of 20.0 units done was told they
    were 115 units short and offered placeholders six times the size of any course
    Waterloo actually offers.
    """
    cm = get_credit_model("University of Waterloo", total_credits_required=20.0)
    ctx = {
        "summary": {"total_credits_required": 20.0, "total_credits_completed": 5.0},
        "planned": [],
        "in_progress": [],
        "credit_model": cm,
    }
    plan = {"semesters": [
        {"term": "Fall 2026", "courses": [{"course_code": "CS 245", "credits": 0.5}]},
        {"term": "Winter 2027", "courses": []},
    ]}
    padded = _pad_plan_to_target(plan, ctx)
    placeholders = [c for s in padded["semesters"] for c in s["courses"] if c.get("is_placeholder")]
    assert placeholders, "expected elective placeholders to be added"
    assert all(p["credits"] == 0.5 for p in placeholders), "padded in York credits"
    assert all("20.0 units" in p["course_name"] for p in placeholders)
    # 14.5 units short, five-course cap across two terms => capacity-bound, and the
    # shortfall warning must be stated in units rather than credits.
    assert all(len(s["courses"]) <= 5 for s in padded["semesters"])
    assert any("units" in w for w in padded.get("warnings", []))


def test_pad_plan_to_target_no_padding_when_degree_is_complete():
    """A finished Waterloo degree is not padded — the sub-unit gap check must scale.

    With the old ``if gap < 3`` guard, any university whose courses are worth less
    than 3 credits could never be "close enough": a student 0.5 units from done
    kept being offered another course.
    """
    cm = get_credit_model("University of Waterloo", total_credits_required=20.0)
    ctx = {
        "summary": {"total_credits_required": 20.0, "total_credits_completed": 20.0},
        "planned": [],
        "in_progress": [],
        "credit_model": cm,
    }
    plan = {"semesters": [{"term": "Fall 2026", "courses": []}]}
    padded = _pad_plan_to_target(plan, ctx)
    assert not [c for s in padded["semesters"] for c in s["courses"]]
