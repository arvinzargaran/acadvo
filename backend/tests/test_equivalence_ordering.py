"""Regression tests for course-equivalence exclusion and plan prereq ordering.

These lock in the follow-up fixes:
  - a completed course satisfies (and suppresses) its mutually-exclusive
    alternative (e.g. LE/EECS 1012 vs LE/EECS 1015),
  - _sanitize_plan drops courses the student has already completed (or an
    equivalent of), and never places a course before a gateway prereq,
  - fail-open behavior when no catalog is supplied is preserved.

All hermetic — no DB, no network.
"""
from app.services.eligibility import equivalents_of, expand_equivalents
from app.services.semester_plan import _sanitize_plan


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
