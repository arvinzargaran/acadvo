import pytest
from datetime import date
from app.services.semester_plan import (
    _current_semester,
    _semester_is_past_or_current,
    _build_future_semesters,
    _is_skipped_season,
)

def test_current_semester():
    # This is a bit tricky because it depends on date.today()
    # But we can check the format
    res = _current_semester()
    assert any(s in res for s in ["Winter", "Summer", "Fall"])
    assert str(date.today().year) in res

@pytest.mark.parametrize("term, expected", [
    ("Fall 2020", True),
    ("Winter 2020", True),
    ("Fall 2025", True), # Assuming "today" is April 2026
    ("Winter 2026", True),
    ("Summer 2026", False), # If current is Winter 2026
    ("Fall 2026", False),
    ("Winter 2027", False),
])
def test_semester_is_past_or_current(term, expected, monkeypatch):
    # Mock date.today() to be 2026-02-15 (Winter 2026)
    class MockDate:
        @classmethod
        def today(cls):
            return date(2026, 2, 15)
    
    monkeypatch.setattr("app.services.semester_plan.date", MockDate)
    
    # Re-verify current semester for the mock
    assert _current_semester() == "Winter 2026"
    
    assert _semester_is_past_or_current(term) == expected

def test_build_future_semesters(monkeypatch):
    class MockDate:
        @classmethod
        def today(cls):
            return date(2026, 2, 15) # Winter 2026
    
    monkeypatch.setattr("app.services.semester_plan.date", MockDate)
    
    # Grad year 2027
    res = _build_future_semesters(2027)
    # Current is Winter 2026. Next should be Summer 2026, Fall 2026, Winter 2027, Summer 2027, Fall 2027
    assert "Summer 2026" in res
    assert "Fall 2026" in res
    assert "Winter 2027" in res
    assert "Summer 2027" in res
    assert "Fall 2027" in res
    assert "Winter 2026" not in res

def test_build_future_semesters_skip(monkeypatch):
    class MockDate:
        @classmethod
        def today(cls):
            return date(2026, 2, 15)
    
    monkeypatch.setattr("app.services.semester_plan.date", MockDate)
    
    res = _build_future_semesters(2027, skip_summers=True)
    assert all("Summer" not in s for s in res)
    assert "Fall 2026" in res
    assert "Winter 2027" in res

def test_is_skipped_season():
    ctx = {"skip_summers": True, "skip_winters": False}
    assert _is_skipped_season("Summer 2026", ctx) is True
    assert _is_skipped_season("Fall 2026", ctx) is False
    assert _is_skipped_season("Winter 2027", ctx) is False
    
    ctx = {"skip_summers": False, "skip_winters": True}
    assert _is_skipped_season("Winter 2027", ctx) is True

from app.services.semester_plan import _sanitize_plan

def test_sanitize_plan(monkeypatch):
    class MockDate:
        @classmethod
        def today(cls):
            return date(2026, 2, 15) # Winter 2026
    
    monkeypatch.setattr("app.services.semester_plan.date", MockDate)
    
    ctx = {
        "all_codes": {"CS 101", "CS 102"}, # CS101 and CS102 already exist
        "skip_summers": True
    }
    
    plan = {
        "semesters": [
            {
                "term": "Winter 2026", # Current, should be dropped
                "courses": [{"course_code": "CS 201"}]
            },
            {
                "term": "Summer 2026", # Opted out, should be dropped
                "courses": [{"course_code": "CS 202"}]
            },
            {
                "term": "Fall 2026", # Valid
                "courses": [
                    {"course_code": "CS 101"}, # Already exists, mark
                    {"course_code": "CS 301"}, # New
                    {"course_code": "CS 302"},
                    {"course_code": "CS 303"},
                    {"course_code": "CS 304"},
                    {"course_code": "CS 305"},
                    {"course_code": "CS 306"}, # 7th course, should be capped to 5
                ]
            }
        ]
    }
    
    cleaned = _sanitize_plan(plan, ctx)
    
    assert len(cleaned["semesters"]) == 1
    assert cleaned["semesters"][0]["term"] == "Fall 2026"
    
    courses = cleaned["semesters"][0]["courses"]
    assert len(courses) == 5 # Capped
    assert courses[0]["course_code"] == "CS 101"
    assert courses[0]["already_in_plan"] is True
    assert courses[1]["course_code"] == "CS 301"
    assert courses[1]["already_in_plan"] is False
    assert "Capped to 5 courses" in cleaned["semesters"][0]["semester_notes"]
