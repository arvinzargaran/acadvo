"""The two aggregations a student reads every day.

`dsa.get_stats` drives the DSA progress panel and feeds the dashboard readiness
score; `schedule.get_all_user_events` is the entire Schedule page. Both were
uncovered — they are pure shaping code with no obvious failure mode, which is
exactly why a wrong count or a dropped event would ship unnoticed.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from app.models.career import TimelineEvent
from app.models.degree import Assessment, Course, CourseStatus
from app.models.career import TimelineCategory
from app.models.dsa import DSAProblem, Difficulty, ProblemStatus
from app.models.project import Milestone, Project
from app.services.dsa import get_stats
from app.services.schedule import get_all_user_events


async def _problem(db, user_id, *, pattern, difficulty, status, solved_at=None):
    p = DSAProblem(
        id=uuid.uuid4(),
        user_id=user_id,
        title=f"Problem {uuid.uuid4().hex[:6]}",
        pattern=pattern,
        difficulty=difficulty,
        status=status,
        solved_at=solved_at,
    )
    db.add(p)
    await db.commit()
    return p


# ── DSA stats ────────────────────────────────────────────────────────


async def test_stats_are_empty_for_a_new_account(db, test_user):
    stats = await get_stats(test_user.id, db)
    assert stats == {
        "total_solved": 0,
        "total_problems": 0,
        "solved_by_difficulty": [],
        "solved_by_pattern": [],
        "weekly_solved": 0,
    }


async def test_only_solved_problems_count_as_solved(db, test_user):
    """Attempted is not solved. Counting it would inflate the readiness score."""
    await _problem(db, test_user.id, pattern="arrays",
                   difficulty=Difficulty.easy, status=ProblemStatus.solved,
                   solved_at=datetime.now(timezone.utc))
    await _problem(db, test_user.id, pattern="arrays",
                   difficulty=Difficulty.hard, status=ProblemStatus.attempted)
    await _problem(db, test_user.id, pattern="graphs",
                   difficulty=Difficulty.medium, status=ProblemStatus.not_started)

    stats = await get_stats(test_user.id, db)
    assert stats["total_problems"] == 3
    assert stats["total_solved"] == 1
    assert stats["solved_by_difficulty"] == [{"difficulty": "easy", "count": 1}]


async def test_patterns_are_ranked_by_count(db, test_user):
    now = datetime.now(timezone.utc)
    for _ in range(3):
        await _problem(db, test_user.id, pattern="graphs",
                       difficulty=Difficulty.medium,
                       status=ProblemStatus.solved, solved_at=now)
    await _problem(db, test_user.id, pattern="arrays",
                   difficulty=Difficulty.easy,
                   status=ProblemStatus.solved, solved_at=now)

    stats = await get_stats(test_user.id, db)
    assert stats["solved_by_pattern"] == [
        {"pattern": "graphs", "count": 3},
        {"pattern": "arrays", "count": 1},
    ]


async def test_weekly_count_uses_a_rolling_seven_days(db, test_user):
    now = datetime.now(timezone.utc)
    await _problem(db, test_user.id, pattern="arrays", difficulty=Difficulty.easy,
                   status=ProblemStatus.solved, solved_at=now - timedelta(days=2))
    await _problem(db, test_user.id, pattern="arrays", difficulty=Difficulty.easy,
                   status=ProblemStatus.solved, solved_at=now - timedelta(days=30))

    stats = await get_stats(test_user.id, db)
    assert stats["total_solved"] == 2
    assert stats["weekly_solved"] == 1


async def test_a_solved_problem_with_no_timestamp_is_not_weekly(db, test_user):
    """Legacy rows have no solved_at. Counting them would silently pad the week."""
    await _problem(db, test_user.id, pattern="arrays", difficulty=Difficulty.easy,
                   status=ProblemStatus.solved, solved_at=None)
    stats = await get_stats(test_user.id, db)
    assert stats["total_solved"] == 1
    assert stats["weekly_solved"] == 0


# ── Schedule aggregation ─────────────────────────────────────────────


async def test_schedule_is_empty_for_a_new_account(db, test_user):
    assert await get_all_user_events(test_user.id, db) == []


async def test_schedule_merges_all_three_sources(db, test_user):
    today = date.today()

    course = Course(id=uuid.uuid4(), user_id=test_user.id, course_code="CS 101",
                    course_name="Intro", credit_value=3.0, status=CourseStatus.in_progress)
    db.add(course)
    await db.commit()
    db.add(Assessment(id=uuid.uuid4(), course_id=course.id, title="Midterm",
                      due_date=today + timedelta(days=3), weight=25.0))

    project = Project(id=uuid.uuid4(), user_id=test_user.id, name="Portfolio site", priority=1)
    db.add(project)
    await db.commit()
    db.add(Milestone(id=uuid.uuid4(), project_id=project.id, title="Ship v1",
                     target_date=today + timedelta(days=10)))

    db.add(TimelineEvent(id=uuid.uuid4(), user_id=test_user.id, title="Shopify deadline",
                         event_date=today + timedelta(days=1),
                         category=TimelineCategory.deadline))
    await db.commit()

    events = await get_all_user_events(test_user.id, db)
    assert {e["category"] for e in events} == {"course", "project", "career"}

    # The course event is prefixed with its course code — the Schedule page shows
    # these in one list, where a bare "Midterm" says nothing.
    course_event = next(e for e in events if e["category"] == "course")
    assert course_event["title"] == "CS 101: Midterm"
    assert course_event["weight"] == 25.0
    assert course_event["status"] == "upcoming"


async def test_schedule_is_sorted_by_date_with_undated_last(db, test_user):
    today = date.today()
    project = Project(id=uuid.uuid4(), user_id=test_user.id, name="P", priority=1)
    db.add(project)
    await db.commit()
    db.add(Milestone(id=uuid.uuid4(), project_id=project.id, title="Later",
                     target_date=today + timedelta(days=5)))
    db.add(Milestone(id=uuid.uuid4(), project_id=project.id, title="Sooner",
                     target_date=today + timedelta(days=1)))
    db.add(Milestone(id=uuid.uuid4(), project_id=project.id, title="Someday",
                     target_date=None))
    await db.commit()

    titles = [e["title"] for e in await get_all_user_events(test_user.id, db)]
    assert titles == ["P: Sooner", "P: Later", "P: Someday"]


async def test_a_past_deadline_is_marked_past(db, test_user):
    db.add(TimelineEvent(id=uuid.uuid4(), user_id=test_user.id, title="Gone",
                         event_date=date.today() - timedelta(days=1),
                         category=TimelineCategory.deadline))
    await db.commit()
    events = await get_all_user_events(test_user.id, db)
    assert events[0]["status"] == "past"
