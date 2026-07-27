"""Regression fixture locking in the whole AI advising-validity fix set.

Scenario "Jordan": a York University CS student who has finished first year with a
cumulative GPA of 5.2 (on York's 9-point scale) but an EECS-major GPA of only 4.0
— BELOW the 4.50 gate York puts on 2000+ EECS courses. This single fixture pins
down every guarantee the earlier waves + the write-safety wave established:

  1. Major-GPA gate math (degree.calculate_major_gpa).
  2. Eligibility evaluation for a gate-blocked and a prereq-blocked course
     (eligibility.evaluate_entry).
  3. The AI ``add_course`` tool REFUSES an ineligible add and writes NO row.
  4. The AI ``update_course_status`` tool is a genuine no-op when nothing changes.
  5. The recommendation path drops fabricated codes and flags gate-blocked ones,
     with the Groq client mocked (fully hermetic — no network).

NOTE: ``app.data.york_cs_catalog.seed_catalog`` uses a Postgres-only
``INSERT ... ON CONFLICT ON CONSTRAINT`` upsert that does not run under the
SQLite test harness, so we seed the SAME catalog rows via plain ORM inserts
below. See the report for details.
"""

import json
import types
import uuid

import pytest

from app.ai.tool_executor import _add_course, _update_course_status, execute_tool
from app.data.york_cs_catalog import YORK_CS_COURSES, YORK_UNIVERSITY
from app.models.catalog import CatalogCourse
from app.models.degree import Course, CourseStatus, DegreeRequirement
from app.models.user import User
from app.services.catalog import get_catalog
from app.services.course_recommendation import generate_recommendations
from app.services.degree import calculate_major_gpa
from app.services.document_parser import normalize_course_code
from app.services.eligibility import (
    evaluate_entry,
    get_completed_codes,
    gpa_by_scope_for_catalog,
)
from app.services.auth import hash_password


# ── First-year transcript. Grades chosen (York 9-pt: A=8,B+=7,B=6,C+=5,C=4,D+=3)
#    so that EECS-major GPA = 40/10 = 4.0 and cumulative GPA = 130/25 = 5.2. ──
_JORDAN_COURSES = [
    # (code, name, credits, grade)  — all COMPLETED
    ("LE/EECS 1001", "Research Directions in Computing", 1.0, "C"),
    ("LE/EECS 1012", "Introduction to Computing: A Net-centric Approach", 3.0, "C"),
    ("LE/EECS 1022", "Introduction to Object Oriented Programming", 3.0, "C+"),
    ("LE/EECS 1019", "Discrete Mathematics for Computer Science", 3.0, "D+"),
    ("SC/MATH 1300", "Differential Calculus with Applications", 3.0, "B"),
    ("SC/MATH 1310", "Integral Calculus with Applications", 3.0, "C+"),
    ("SC/BIOL 1000", "Biological Science", 3.0, "C"),
    ("AP/ECON 1000", "Introduction to Microeconomics", 3.0, "B+"),
    ("AP/ECON 1010", "Introduction to Macroeconomics", 3.0, "A"),
]


async def _seed_york_catalog(db):
    """Insert the York CS catalog rows directly (SQLite-safe equivalent of
    ``seed_catalog``, which relies on a Postgres-only upsert)."""
    for c in YORK_CS_COURSES:
        db.add(
            CatalogCourse(
                id=uuid.uuid4(),
                university=YORK_UNIVERSITY,
                course_code=c["course_code"],
                course_name=c["course_name"],
                credits=c["credits"],
                subject_faculty=c.get("subject_faculty"),
                prerequisites=c.get("prerequisites") or [],
                gpa_gate=c.get("gpa_gate"),
            )
        )
    await db.commit()


@pytest.fixture
async def jordan(db):
    """York CS student, first year done, EECS GPA 4.0 (below the 4.50 gate)."""
    user = User(
        id=uuid.uuid4(),
        email="jordan@my.yorku.ca",
        hashed_password=hash_password("testpass123"),
        full_name="Jordan Lee",
        university=YORK_UNIVERSITY,
        program="Computer Science",
        start_year=2024,
        expected_graduation_year=2028,
    )
    db.add(user)
    await db.flush()

    # Requirement buckets
    for bucket_name, credits in [
        ("Computer Science Core", 42.0),
        ("Mathematics", 12.0),
        ("General Education", 12.0),
    ]:
        db.add(
            DegreeRequirement(
                user_id=user.id,
                bucket_name=bucket_name,
                credits_required=credits,
            )
        )

    # Completed first-year courses
    for code, name, credits, grade in _JORDAN_COURSES:
        db.add(
            Course(
                user_id=user.id,
                course_code=code,
                course_name=name,
                credit_value=credits,
                status=CourseStatus.completed,
                term="Fall 2024",
                grade=grade,
            )
        )

    await _seed_york_catalog(db)
    await db.commit()
    return user


# ── 1. Major-GPA gate math ───────────────────────────────────────────

async def test_eecs_major_gpa_below_gate(jordan, db):
    result = await calculate_major_gpa(jordan.id, db, faculty_prefix="EECS")
    assert result["gpa"] == 4.0
    assert result["meets_gate"] is False


# ── 2. Eligibility evaluation (gate-blocked + prereq-blocked) ─────────

async def test_evaluate_entry_gate_and_prereq_blocks(jordan, db):
    catalog = await get_catalog(YORK_UNIVERSITY, db, user_id=jordan.id)
    satisfied = await get_completed_codes(jordan.id, db)
    gpa_by_scope = await gpa_by_scope_for_catalog(catalog, jordan.id, db)

    # LE/EECS 2030: prereq (1022) is met, so it is BLOCKED by the GPA gate.
    reason_2030 = evaluate_entry(catalog["LE/EECS 2030"], satisfied, gpa_by_scope)
    assert reason_2030 is not None
    assert "4.50" in reason_2030 and "GPA" in reason_2030

    # LE/EECS 2101: needs 1019 AND 2030; 2030 is missing → prereq block first.
    reason_2101 = evaluate_entry(catalog["LE/EECS 2101"], satisfied, gpa_by_scope)
    assert reason_2101 is not None
    assert "LE/EECS 2030" in reason_2101
    assert "prerequisite" in reason_2101.lower()


# ── 3. add_course REFUSES an ineligible add and writes no row ─────────

async def test_add_course_refuses_gated_course(jordan, db):
    before = (await db.execute(select_courses(jordan.id))).scalars().all()
    before_count = len(before)

    result = await _add_course(
        {
            "course_code": "EECS 2030",  # non-canonical on purpose → normalized
            "course_name": "Model's made-up name",
            "credit_value": 9.9,  # model's wrong credits — must never be trusted
            "status": "planned",
            "term": "Winter 2025",
        },
        jordan.id,
        None,
        db,
    )

    assert "error" in result
    assert result.get("blocked_reason") is not None
    assert "Cannot add LE/EECS 2030" in result["error"]
    assert "4.50" in result["error"]

    # No row was created (fail-closed).
    after = (await db.execute(select_courses(jordan.id))).scalars().all()
    assert len(after) == before_count
    assert not any(normalize_course_code(c.course_code) == "LE/EECS 2030" for c in after)


async def test_add_course_dedupes_existing_code(jordan, db):
    """Re-adding a code the student already has is refused, not duplicated."""
    result = await _add_course(
        {
            "course_code": "EECS 1012",  # already completed by Jordan
            "course_name": "whatever",
            "credit_value": 3.0,
        },
        jordan.id,
        None,
        db,
    )
    assert result.get("duplicate") is True
    assert "already" in result["error"]


# ── 4. update_course_status is a no-op when nothing changes ───────────

async def test_update_course_status_noop(jordan, db):
    course = (
        (await db.execute(select_courses(jordan.id))).scalars().all()
    )[0]
    original_status = course.status
    original_grade = course.grade

    result = await _update_course_status(
        {
            "course_id": str(course.id),
            "status": course.status.value,
            "grade": course.grade,
        },
        jordan.id,
        None,
        db,
    )

    assert result["success"] is True
    assert result.get("no_op") is True

    # Nothing changed on disk.
    await db.refresh(course)
    assert course.status == original_status
    assert course.grade == original_grade


# ── 5. Recommendation path: drop fabricated code, flag gated code ─────

class _MockChoice:
    def __init__(self, content):
        self.message = types.SimpleNamespace(content=content)


class _MockCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, *args, **kwargs):
        return types.SimpleNamespace(choices=[_MockChoice(self._content)])


class _MockGroqClient:
    def __init__(self, content):
        self.chat = types.SimpleNamespace(completions=_MockCompletions(content))


async def test_recommendations_drop_fabricated_flag_gated(jordan, db, monkeypatch):
    payload = json.dumps(
        [
            {
                "course_code": "EECS 4040",  # fabricated — not in the catalog
                "course_name": "Totally Real Course",
                "credits": 3.0,
                "requirement_bucket": "Computer Science Core",
                "reasoning": "hallucinated",
                "career_relevance": "n/a",
                "prerequisite_notes": "",
                "priority": "high",
            },
            {
                "course_code": "LE/EECS 2030",  # real, but gate-blocked for Jordan
                "course_name": "Advanced Object Oriented Programming",
                "credits": 3.0,
                "requirement_bucket": "Computer Science Core",
                "reasoning": "core course",
                "career_relevance": "software roles",
                "prerequisite_notes": "",
                "priority": "high",
            },
        ]
    )
    monkeypatch.setattr(
        "app.services.course_recommendation.get_groq_client",
        lambda: _MockGroqClient(payload),
    )

    recs = await generate_recommendations(
        jordan.id, "Winter 2025", "both", None, db
    )

    codes = {r.course_code for r in recs}
    # Fabricated code dropped.
    assert not any("4040" in c for c in codes)
    # Gated real code kept but flagged.
    assert "LE/EECS 2030" in codes
    gated = next(r for r in recs if r.course_code == "LE/EECS 2030")
    assert gated.prerequisite_notes is not None
    assert "BLOCKED" in gated.prerequisite_notes
    assert "4.50" in gated.prerequisite_notes


# ── helper ───────────────────────────────────────────────────────────

def select_courses(user_id):
    from sqlalchemy import select

    return select(Course).where(Course.user_id == user_id)
