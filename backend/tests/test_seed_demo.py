"""The demo account is the first thing a visitor sees, so its data has to cohere.

These assertions are about the fabricated dataset itself, not the database: a
course pointing at a requirement bucket that does not exist, or a completed
course with no grade, produces a demo that contradicts the product's own rules.
"""

from app.models.degree import CourseStatus
from app.scripts.seed_demo import COURSES, DEMO_EMAIL, PROJECTS, REQUIREMENTS, TIMELINE


def test_every_course_maps_to_a_declared_requirement_bucket():
    buckets = {name for name, _credits, _description in REQUIREMENTS}
    referenced = {course[6] for course in COURSES}
    assert referenced <= buckets, f"courses reference unknown buckets: {referenced - buckets}"


def test_every_course_status_is_real():
    valid = {status.value for status in CourseStatus}
    assert {course[3] for course in COURSES} <= valid


def test_completed_courses_carry_a_grade_and_unfinished_ones_do_not():
    """The parser bug this guards against shipped once: a course marked complete
    with no grade silently counts toward progress and GPA is computed from it."""
    for code, _name, _credits, status, _term, grade, _bucket in COURSES:
        if status == "completed":
            assert grade, f"{code} is completed with no grade"
        else:
            assert grade is None, f"{code} is {status} but carries a grade"


def test_earned_credits_do_not_exceed_the_declared_requirements():
    required = sum(credits for _name, credits, _description in REQUIREMENTS)
    completed = sum(c[2] for c in COURSES if c[3] == "completed")
    assert 0 < completed < required, "demo should be partway through, not done or empty"


def test_the_demo_shows_every_course_status_and_a_full_career_pipeline():
    """An empty column teaches a visitor nothing about what the column is for."""
    statuses = {course[3] for course in COURSES}
    assert {"completed", "in_progress", "planned"} <= statuses

    from app.scripts.seed_demo import CAREER_TARGETS
    from app.models.career import CareerStatus

    assert {t[3] for t in CAREER_TARGETS} == set(CareerStatus)


def test_projects_and_timeline_are_populated():
    assert len(PROJECTS) >= 2
    assert all(p["milestones"] for p in PROJECTS)
    assert any(event[3] for event in TIMELINE), "at least one hard deadline"


def test_demo_account_is_not_a_real_looking_address():
    assert DEMO_EMAIL.endswith("@acadvo.app")
