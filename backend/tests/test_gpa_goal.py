"""Tests for the reverse GPA goal-projection endpoints.

Covers the needed-average math, the achievable / impossible / already-met flags,
the divide-by-zero guard, and the major-gate variant. Uses the same authed-client
pattern as ``test_degree.py`` / ``test_assessment_grades.py``.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.auth import create_access_token, hash_password


async def _make_client(app, db, university="University of Toronto"):
    """Create a user with a given university and return an authenticated client."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("testpass123"),
        full_name="Goal Test User",
        university=university,
        program="Computer Science",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": token},
    )


async def _add_course(client, code, grade, credits=3.0, term="Fall 2025", status="completed"):
    resp = await client.post("/degree/courses", json={
        "course_code": code,
        "course_name": f"Course {code}",
        "credit_value": credits,
        "status": status,
        "grade": grade,
        "term": term,
    })
    assert resp.status_code == 201


# ── Cumulative goal: math + flags ────────────────────────────────────

async def test_goal_needed_average_math(app, db):
    """UofT: 6 completed credits at 3.0 GPA. Target 3.5 over 6 more credits →
    needed = (3.5*12 - 3.0*6) / 6 = (42 - 18)/6 = 4.0."""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        await _add_course(c, "CSC108", "B")  # B = 3.0
        await _add_course(c, "CSC148", "B")  # B = 3.0
        resp = await c.get("/degree/gpa/goal", params={"target": 3.5, "remaining_credits": 6})
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_cumulative_gpa"] == 3.0
        assert data["total_credits_completed"] == 6.0
        assert data["needed_average"] == 4.0
        assert data["achievable"] is True   # 4.0 <= 4.0 scale_max
        assert data["already_met"] is False
        assert data["scale_max"] == 4.0


async def test_goal_impossible(app, db):
    """Target above what's reachable → needed_average exceeds scale_max."""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        await _add_course(c, "CSC108", "C")  # C = 2.0
        await _add_course(c, "CSC148", "C")  # C = 2.0 → cumulative 2.0
        # Need to reach 3.9 over just 3 more credits: (3.9*9 - 2.0*6)/3 = 7.7 > 4.0
        resp = await c.get("/degree/gpa/goal", params={"target": 3.9, "remaining_credits": 3})
        data = resp.json()
        assert data["achievable"] is False
        assert data["already_met"] is False
        assert data["needed_average"] > data["scale_max"]


async def test_goal_already_met(app, db):
    """Current GPA high enough that even zeros on the (small) remaining load keep
    the cumulative at/above target → already met (raw requirement <= 0).
    Completed 6cr @ 4.0, target 3.0 over just 1 more credit:
    needed = (3.0*7 - 4.0*6)/1 = -3 <= 0."""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        await _add_course(c, "CSC108", "A")  # A = 4.0
        await _add_course(c, "CSC148", "A")  # A = 4.0 → cumulative 4.0
        resp = await c.get("/degree/gpa/goal", params={"target": 3.0, "remaining_credits": 1})
        data = resp.json()
        assert data["already_met"] is True
        assert data["achievable"] is True
        assert data["needed_average"] == 0.0  # clamped to >= 0


async def test_goal_no_completed_courses(app, db):
    """No graded courses → completed side is 0, so you simply need target."""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        resp = await c.get("/degree/gpa/goal", params={"target": 3.5, "remaining_credits": 12})
        data = resp.json()
        assert data["current_cumulative_gpa"] is None
        assert data["total_credits_completed"] == 0.0
        assert data["needed_average"] == 3.5
        assert data["achievable"] is True


async def test_goal_divide_by_zero_guard(app, db):
    """remaining_credits <= 0 → clean 400."""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        await _add_course(c, "CSC108", "A")
        resp = await c.get("/degree/gpa/goal", params={"target": 3.5, "remaining_credits": 0})
        assert resp.status_code == 400
        assert "remaining_credits" in resp.json()["detail"]

        neg = await c.get("/degree/gpa/goal", params={"target": 3.5, "remaining_credits": -4})
        assert neg.status_code == 400


async def test_goal_negative_target_rejected(app, db):
    """A negative target is rejected by query validation (422)."""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        resp = await c.get("/degree/gpa/goal", params={"target": -1, "remaining_credits": 6})
        assert resp.status_code == 422


# ── Uses the university-specific scale, not a hardcoded 4.0 ───────────

async def test_goal_respects_york_scale(app, db):
    """York's 9-point scale: a needed average of 7.5 must be flagged achievable
    (<= 9.0), which a hardcoded 4.0 max would wrongly reject."""
    c = await _make_client(app, db, "York University")
    async with c:
        await _add_course(c, "EECS1001", "C")  # York C = 4.0
        await _add_course(c, "EECS1002", "C")  # cumulative 4.0 over 6 credits
        # Target 5.75 over 6 more: (5.75*12 - 4.0*6)/6 = (69 - 24)/6 = 7.5
        resp = await c.get("/degree/gpa/goal", params={"target": 5.75, "remaining_credits": 6})
        data = resp.json()
        assert data["scale_max"] == 9.0
        assert data["needed_average"] == 7.5
        assert data["achievable"] is True


# ── Major-gate variant ───────────────────────────────────────────────

async def test_major_goal_below_gate(app, db):
    """York EECS student with a 4.0 EECS GPA over 6 EECS credits must average
    (4.5*12 - 4.0*6)/6 = (54 - 24)/6 = 5.0 on the next 6 EECS credits to hit 4.50."""
    c = await _make_client(app, db, "York University")
    async with c:
        await _add_course(c, "LE/EECS 1012", "C")  # York C = 4.0
        await _add_course(c, "LE/EECS 1022", "C")  # EECS GPA 4.0 over 6 credits
        await _add_course(c, "SC/MATH 1300", "A")  # non-EECS, ignored for major scope
        resp = await c.get("/degree/gpa/goal/major", params={"remaining_credits": 6})
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "EECS"
        assert data["gate"] == 4.5
        assert data["current_major_gpa"] == 4.0
        assert data["major_credits_completed"] == 6.0
        assert data["needed_average"] == 5.0
        assert data["meets_gate"] is False
        assert data["already_met"] is False
        assert data["achievable"] is True
        assert data["scale_max"] == 9.0


async def test_major_goal_already_meets_gate(app, db):
    """A student already above the gate is flagged already_met."""
    c = await _make_client(app, db, "York University")
    async with c:
        await _add_course(c, "LE/EECS 2030", "A")  # York A = 8.0, above 4.50
        resp = await c.get("/degree/gpa/goal/major", params={"remaining_credits": 6})
        data = resp.json()
        assert data["meets_gate"] is True
        assert data["already_met"] is True
        assert data["achievable"] is True


async def test_major_goal_divide_by_zero_guard(app, db):
    c = await _make_client(app, db, "York University")
    async with c:
        await _add_course(c, "LE/EECS 1012", "C")
        resp = await c.get("/degree/gpa/goal/major", params={"remaining_credits": 0})
        assert resp.status_code == 400
