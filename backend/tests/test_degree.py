"""Tests for degree endpoints: requirements, courses, summary, GPA."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.auth import create_access_token, hash_password


# ── Requirements ─────────────────────────────────────────────────────

async def test_create_requirement(auth_client):
    resp = await auth_client.post("/degree/requirements", json={
        "bucket_name": "Core CS",
        "credits_required": 30.0,
        "description": "Core computer science courses",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["bucket_name"] == "Core CS"
    assert data["credits_required"] == 30.0


# ── Courses ──────────────────────────────────────────────────────────

async def test_create_course(auth_client):
    resp = await auth_client.post("/degree/courses", json={
        "course_code": "CS101",
        "course_name": "Intro to Computer Science",
        "credit_value": 3.0,
        "status": "planned",
        "term": "Fall 2026",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["course_code"] == "CS101"
    assert data["status"] == "planned"
    assert data["term"] == "Fall 2026"


# ── Summary ──────────────────────────────────────────────────────────

async def test_empty_summary(auth_client):
    resp = await auth_client.get("/degree/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["buckets"] == []
    assert data["total_credits_required"] == 0.0
    assert data["total_credits_completed"] == 0.0
    assert data["overall_percentage"] == 0.0


async def test_summary_with_courses(auth_client):
    # Create a requirement bucket
    req_resp = await auth_client.post("/degree/requirements", json={
        "bucket_name": "Science Breadth",
        "credits_required": 6.0,
    })
    bucket_id = req_resp.json()["id"]

    # Add a completed course in that bucket
    await auth_client.post("/degree/courses", json={
        "course_code": "BIO101",
        "course_name": "Intro Biology",
        "credit_value": 3.0,
        "status": "completed",
        "grade": "A",
        "requirement_bucket_id": bucket_id,
    })

    resp = await auth_client.get("/degree/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_credits_required"] == 6.0
    assert data["total_credits_completed"] == 3.0
    assert data["overall_percentage"] == 50.0
    assert len(data["buckets"]) == 1
    assert data["buckets"][0]["credits_completed"] == 3.0
    assert data["buckets"][0]["credits_remaining"] == 3.0


# ── Update Course ────────────────────────────────────────────────────

async def test_update_course_status(auth_client):
    # Create a course
    create_resp = await auth_client.post("/degree/courses", json={
        "course_code": "MATH201",
        "course_name": "Linear Algebra",
        "credit_value": 3.0,
        "status": "in_progress",
    })
    course_id = create_resp.json()["id"]

    # Update to completed with a grade
    resp = await auth_client.put(f"/degree/courses/{course_id}", json={
        "status": "completed",
        "grade": "A+",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["grade"] == "A+"


# ── GPA Calculator ──────────────────────────────────────────────────

async def _make_client(app, db, university):
    """Create a user with a given university and return an authenticated client."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("testpass123"),
        full_name="GPA Test User",
        university=university,
        program="Computer Science",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    transport = ASGITransport(app=app)
    client = AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": token},
    )
    return client


async def test_gpa_york_scale(app, db):
    """York A+(9)*3cr + B(6)*3cr → cumulative = (27+18)/6 = 7.5"""
    c = await _make_client(app, db, "York University")
    async with c:
        await c.post("/degree/courses", json={
            "course_code": "EECS1001", "course_name": "Course A",
            "credit_value": 3.0, "status": "completed", "grade": "A+", "term": "Fall 2025",
        })
        await c.post("/degree/courses", json={
            "course_code": "EECS1002", "course_name": "Course B",
            "credit_value": 3.0, "status": "completed", "grade": "B", "term": "Fall 2025",
        })
        resp = await c.get("/degree/gpa")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cumulative_gpa"] == 7.5
        assert data["scale_max"] == 9.0
        assert data["using_fallback"] is False
        assert "York" in data["scale_name"]
        assert data["graded_course_count"] == 2
        assert data["total_credits_completed"] == 6.0


async def test_gpa_uoft_scale(app, db):
    """UofT A+(4.0)*3cr + B+(3.3)*3cr → cumulative = (12+9.9)/6 = 3.65"""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        await c.post("/degree/courses", json={
            "course_code": "CSC108", "course_name": "Intro CS",
            "credit_value": 3.0, "status": "completed", "grade": "A+", "term": "Fall 2025",
        })
        await c.post("/degree/courses", json={
            "course_code": "MAT137", "course_name": "Calculus",
            "credit_value": 3.0, "status": "completed", "grade": "B+", "term": "Fall 2025",
        })
        resp = await c.get("/degree/gpa")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cumulative_gpa"] == 3.65
        assert data["scale_max"] == 4.0
        assert data["using_fallback"] is False


async def test_gpa_unknown_university(app, db):
    """Unknown university should fall back to 4.0 scale."""
    c = await _make_client(app, db, "Some Unknown School")
    async with c:
        await c.post("/degree/courses", json={
            "course_code": "CS101", "course_name": "Intro",
            "credit_value": 3.0, "status": "completed", "grade": "A", "term": "Fall 2025",
        })
        resp = await c.get("/degree/gpa")
        assert resp.status_code == 200
        data = resp.json()
        assert data["using_fallback"] is True
        assert data["cumulative_gpa"] == 4.0
        assert data["scale_max"] == 4.0


async def test_gpa_excludes_in_progress(app, db):
    """In-progress courses must not be included in GPA calculation."""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        await c.post("/degree/courses", json={
            "course_code": "CSC108", "course_name": "Intro CS",
            "credit_value": 3.0, "status": "completed", "grade": "A", "term": "Fall 2025",
        })
        await c.post("/degree/courses", json={
            "course_code": "CSC148", "course_name": "Intro CS 2",
            "credit_value": 3.0, "status": "in_progress", "grade": "B", "term": "Winter 2026",
        })
        resp = await c.get("/degree/gpa")
        data = resp.json()
        assert data["graded_course_count"] == 1
        assert data["total_credits_completed"] == 3.0
        assert data["cumulative_gpa"] == 4.0


async def test_gpa_no_grades(app, db):
    """No graded courses → cumulative_gpa is None."""
    c = await _make_client(app, db, "University of Toronto")
    async with c:
        await c.post("/degree/courses", json={
            "course_code": "CSC108", "course_name": "Intro CS",
            "credit_value": 3.0, "status": "planned",
        })
        resp = await c.get("/degree/gpa")
        data = resp.json()
        assert data["cumulative_gpa"] is None
        assert data["graded_course_count"] == 0
        assert data["term_gpas"] == []


async def test_gpa_term_breakdown(app, db):
    """Two terms produce correct per-term GPAs."""
    c = await _make_client(app, db, "York University")
    async with c:
        # Fall: A+ (9.0)
        await c.post("/degree/courses", json={
            "course_code": "EECS1001", "course_name": "Course A",
            "credit_value": 3.0, "status": "completed", "grade": "A+", "term": "Fall 2025",
        })
        # Winter: C+ (5.0), B+ (7.0) → (15+21)/6 = 6.0
        await c.post("/degree/courses", json={
            "course_code": "EECS2001", "course_name": "Course B",
            "credit_value": 3.0, "status": "completed", "grade": "C+", "term": "Winter 2026",
        })
        await c.post("/degree/courses", json={
            "course_code": "EECS2002", "course_name": "Course C",
            "credit_value": 3.0, "status": "completed", "grade": "B+", "term": "Winter 2026",
        })
        resp = await c.get("/degree/gpa")
        data = resp.json()
        terms = {t["term"]: t for t in data["term_gpas"]}
        assert terms["Fall 2025"]["gpa"] == 9.0
        assert terms["Winter 2026"]["gpa"] == 6.0
        assert terms["Winter 2026"]["course_count"] == 2
        assert data["highest_term"]["term"] == "Fall 2025"
        assert data["lowest_term"]["term"] == "Winter 2026"


# ── Cross-tenant reference protection ────────────────────────────────

async def test_course_cannot_reference_foreign_bucket(auth_client, app, db):
    """A user must not be able to link a course to another user's requirement bucket."""
    # Second user creates their own bucket
    other = await _make_client(app, db, "York University")
    async with other as oc:
        r = await oc.post("/degree/requirements", json={
            "bucket_name": "Their Bucket",
            "credits_required": 12.0,
        })
        foreign_bucket_id = r.json()["id"]

    # First user (auth_client) tries to reference the foreign bucket
    resp = await auth_client.post("/degree/courses", json={
        "course_code": "CSC999",
        "course_name": "Sneaky Course",
        "credit_value": 3.0,
        "requirement_bucket_id": foreign_bucket_id,
    })
    assert resp.status_code == 404


async def test_course_update_cannot_reference_foreign_bucket(auth_client, app, db):
    other = await _make_client(app, db, "York University")
    async with other as oc:
        r = await oc.post("/degree/requirements", json={
            "bucket_name": "Their Bucket 2",
            "credits_required": 12.0,
        })
        foreign_bucket_id = r.json()["id"]

    # First user creates a legit course, then tries to repoint it to the foreign bucket
    c = await auth_client.post("/degree/courses", json={
        "course_code": "CSC111",
        "course_name": "My Course",
        "credit_value": 3.0,
    })
    course_id = c.json()["id"]
    resp = await auth_client.put(f"/degree/courses/{course_id}", json={
        "requirement_bucket_id": foreign_bucket_id,
    })
    assert resp.status_code == 404


async def test_course_own_bucket_still_works(auth_client):
    r = await auth_client.post("/degree/requirements", json={
        "bucket_name": "My Own Bucket",
        "credits_required": 6.0,
    })
    bucket_id = r.json()["id"]
    resp = await auth_client.post("/degree/courses", json={
        "course_code": "CSC222",
        "course_name": "Legit Course",
        "credit_value": 3.0,
        "requirement_bucket_id": bucket_id,
    })
    assert resp.status_code == 201
