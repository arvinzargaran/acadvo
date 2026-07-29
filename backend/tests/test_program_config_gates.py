"""Locks in the de-hardcoding of York/EECS assumptions and the verified-vs-
best-effort honesty layer (make-it-real roadmap, Tier 1).

Guarantees:
  1. Major-GPA gates are config-driven per university, not hardcoded to EECS.
  2. calculate_gpa returns major_gpas ONLY for universities that define a gate —
     a non-York student is not shown a phantom EECS gate.
  3. has_seeded_catalog distinguishes verified from best-effort universities.
  4. The AI system prompt is honest: it claims a VERIFIED catalog + names the real
     gate for York, but says NO verified catalog / best-effort for an unseeded
     university, and never mentions EECS there.
"""
import uuid

import pytest

from app.ai.context import build_system_prompt
from app.data.program_config import get_major_gpa_gates
from app.models.catalog import CatalogCourse
from app.models.degree import Course, CourseStatus
from app.models.user import User
from app.services.auth import hash_password
from app.services.catalog import has_seeded_catalog
from app.services.degree import calculate_gpa


async def _make_user(db, *, university, program, courses):
    """Create a user with a set of completed graded courses. ``courses`` is a list
    of (code, name, credits, grade)."""
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Test Student",
        university=university,
        program=program,
        start_year=2024,
        expected_graduation_year=2028,
    )
    db.add(user)
    await db.flush()
    for code, name, credits, grade in courses:
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
    await db.commit()
    return user


# ── 1. Config-driven gates ───────────────────────────────────────────

def test_york_has_eecs_gate():
    gates = get_major_gpa_gates("York University")
    assert len(gates) == 1
    assert gates[0]["scope"] == "EECS"
    assert gates[0]["min"] == 4.50


def test_other_universities_have_no_gate():
    assert get_major_gpa_gates("University of Toronto") == []
    assert get_major_gpa_gates("University of Waterloo") == []
    assert get_major_gpa_gates(None) == []
    assert get_major_gpa_gates("") == []


# ── 2. calculate_gpa only emits configured gates ─────────────────────

async def test_york_student_gets_eecs_major_gpa(db):
    user = await _make_user(
        db,
        university="York University",
        program="Computer Science",
        courses=[
            ("LE/EECS 1012", "Intro to Computing", 3.0, "B"),
            ("LE/EECS 1022", "Intro to OOP", 3.0, "C+"),
        ],
    )
    data = await calculate_gpa(user.id, db)
    assert len(data["major_gpas"]) == 1
    mg = data["major_gpas"][0]
    assert mg["scope"] == "EECS"
    assert mg["gate"] == 4.50
    assert mg["gpa"] is not None


async def test_non_york_student_gets_no_major_gpa(db):
    """The core de-hardcoding guarantee: a UofT CS student is NOT handed York's
    EECS gate."""
    user = await _make_user(
        db,
        university="University of Toronto",
        program="Computer Science",
        courses=[
            ("CSC148", "Intro to Computer Science", 0.5, "A"),
            ("MAT137", "Calculus", 1.0, "B+"),
        ],
    )
    data = await calculate_gpa(user.id, db)
    assert data["major_gpas"] == []


# ── 3. Verified vs best-effort catalog detection ─────────────────────

async def test_has_seeded_catalog(db):
    db.add(
        CatalogCourse(
            id=uuid.uuid4(),
            university="York University",
            course_code="LE/EECS 2030",
            course_name="Advanced OOP",
            credits=3.0,
            subject_faculty="EECS",
            prerequisites=[],
            gpa_gate=None,
        )
    )
    await db.commit()
    assert await has_seeded_catalog("York University", db) is True
    assert await has_seeded_catalog("University of Toronto", db) is False
    assert await has_seeded_catalog(None, db) is False


# ── 4. The AI prompt is honest about what it knows ───────────────────

async def test_prompt_verified_for_seeded_university(db):
    user = await _make_user(
        db,
        university="York University",
        program="Computer Science",
        courses=[("LE/EECS 1012", "Intro to Computing", 3.0, "B")],
    )
    db.add(
        CatalogCourse(
            id=uuid.uuid4(),
            university="York University",
            course_code="LE/EECS 2030",
            course_name="Advanced OOP",
            credits=3.0,
            subject_faculty="EECS",
            prerequisites=[],
            gpa_gate=None,
        )
    )
    await db.commit()
    prompt = await build_system_prompt(user.id, db)
    assert "VERIFIED" in prompt
    assert "EECS" in prompt
    assert "4.50" in prompt


async def test_prompt_best_effort_for_unseeded_university(db):
    user = await _make_user(
        db,
        university="University of Toronto",
        program="Computer Science",
        courses=[("CSC148", "Intro to Computer Science", 0.5, "A")],
    )
    prompt = await build_system_prompt(user.id, db)
    assert "NO verified catalog" in prompt
    assert "best-effort" in prompt
    # Must NOT leak York's EECS gate to a UofT student.
    assert "EECS" not in prompt
