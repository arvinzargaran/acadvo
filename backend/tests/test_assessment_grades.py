"""Tests for assessment CRUD, earned scores, and final-grade projection."""

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
        full_name="Grade Test User",
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


async def _make_course(client, code="CSC207"):
    resp = await client.post("/degree/courses", json={
        "course_code": code,
        "course_name": "Software Design",
        "credit_value": 3.0,
        "status": "in_progress",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Assessment CRUD ──────────────────────────────────────────────────

async def test_create_assessment(auth_client):
    course_id = await _make_course(auth_client)
    resp = await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Midterm",
        "weight": 40.0,
        "category": "exam",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Midterm"
    assert data["weight"] == 40.0
    assert data["score"] is None
    assert data["category"] == "exam"


async def test_update_assessment_score(auth_client):
    course_id = await _make_course(auth_client)
    create = await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Quiz 1", "weight": 10.0, "category": "quiz",
    })
    aid = create.json()["id"]
    resp = await auth_client.put(f"/degree/assessments/{aid}", json={"score": 92.5})
    assert resp.status_code == 200
    assert resp.json()["score"] == 92.5
    # Other fields untouched
    assert resp.json()["title"] == "Quiz 1"
    assert resp.json()["weight"] == 10.0


async def test_delete_assessment(auth_client):
    course_id = await _make_course(auth_client)
    create = await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Assignment 1", "weight": 15.0,
    })
    aid = create.json()["id"]
    resp = await auth_client.delete(f"/degree/assessments/{aid}")
    assert resp.status_code == 204
    listing = await auth_client.get(f"/degree/courses/{course_id}/assessments")
    assert listing.json() == []


async def test_score_validation_rejects_out_of_range(auth_client):
    course_id = await _make_course(auth_client)
    # On create
    resp = await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Bad", "weight": 10.0, "score": 150.0,
    })
    assert resp.status_code == 422
    # On update
    create = await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Ok", "weight": 10.0,
    })
    aid = create.json()["id"]
    resp = await auth_client.put(f"/degree/assessments/{aid}", json={"score": -5})
    assert resp.status_code == 422


# ── Projection math ──────────────────────────────────────────────────

async def test_projection_current_and_projected(auth_client):
    """Midterm 40% scored 80, final 60% ungraded → current standing 80,
    projected final 80 (maintained), UofT 80% → A- (3.7)."""
    course_id = await _make_course(auth_client)
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Midterm", "weight": 40.0, "score": 80.0, "category": "exam",
    })
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Final", "weight": 60.0, "category": "exam",
    })
    resp = await auth_client.get(f"/degree/courses/{course_id}/grade-projection")
    assert resp.status_code == 200
    data = resp.json()
    assert data["graded_weight"] == 40.0
    assert data["total_weight"] == 100.0
    assert data["remaining_weight"] == 60.0
    assert data["current_weighted_pct"] == 80.0
    assert data["projected_final_pct"] == 80.0
    assert data["projected_letter"] == "A-"
    assert data["projected_gpa_points"] == 3.7


async def test_projection_target_achievable(auth_client):
    """Earned 32 pts (40%@80); to hit 85 final over 60% remaining need 88.33%."""
    course_id = await _make_course(auth_client)
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Midterm", "weight": 40.0, "score": 80.0,
    })
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Final", "weight": 60.0,
    })
    resp = await auth_client.get(f"/degree/courses/{course_id}/grade-projection?target=85")
    data = resp.json()
    assert data["target_final_pct"] == 85.0
    assert data["score_needed_on_remaining"] == pytest.approx(88.33, abs=0.01)
    assert data["target_achievable"] is True
    assert data["target_already_secured"] is False


async def test_projection_target_impossible(auth_client):
    """Target 95 over 60% remaining needs 105% → impossible."""
    course_id = await _make_course(auth_client)
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Midterm", "weight": 40.0, "score": 80.0,
    })
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Final", "weight": 60.0,
    })
    resp = await auth_client.get(f"/degree/courses/{course_id}/grade-projection?target=95")
    data = resp.json()
    assert data["target_achievable"] is False
    assert data["score_needed_on_remaining"] == 105.0


async def test_projection_all_graded_secured(auth_client):
    """Everything graded → remaining 0; target below projected is secured."""
    course_id = await _make_course(auth_client)
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Midterm", "weight": 40.0, "score": 80.0,
    })
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Final", "weight": 60.0, "score": 90.0,
    })
    resp = await auth_client.get(f"/degree/courses/{course_id}/grade-projection?target=80")
    data = resp.json()
    assert data["remaining_weight"] == 0.0
    assert data["projected_final_pct"] == 86.0  # 32 + 54
    assert data["score_needed_on_remaining"] is None
    assert data["target_already_secured"] is True
    assert data["target_achievable"] is True


async def test_projection_no_grades(auth_client):
    """No scored assessments → current/projected are null."""
    course_id = await _make_course(auth_client)
    await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Midterm", "weight": 40.0,
    })
    resp = await auth_client.get(f"/degree/courses/{course_id}/grade-projection")
    data = resp.json()
    assert data["current_weighted_pct"] is None
    assert data["projected_final_pct"] is None
    assert data["projected_letter"] is None


# ── Ownership isolation ──────────────────────────────────────────────

async def test_user_cannot_edit_foreign_assessment(auth_client, app, db):
    """User B must not be able to update or delete user A's assessment."""
    course_id = await _make_course(auth_client, code="CSC301")
    create = await auth_client.post(f"/degree/courses/{course_id}/assessments", json={
        "title": "Secret Exam", "weight": 50.0,
    })
    aid = create.json()["id"]

    other = await _make_client(app, db, "York University")
    async with other as oc:
        upd = await oc.put(f"/degree/assessments/{aid}", json={"score": 100.0})
        assert upd.status_code == 404
        dele = await oc.delete(f"/degree/assessments/{aid}")
        assert dele.status_code == 404
        proj = await oc.get(f"/degree/courses/{course_id}/grade-projection")
        assert proj.status_code == 404


async def test_user_cannot_add_assessment_to_foreign_course(auth_client, app, db):
    course_id = await _make_course(auth_client, code="CSC302")
    other = await _make_client(app, db, "York University")
    async with other as oc:
        resp = await oc.post(f"/degree/courses/{course_id}/assessments", json={
            "title": "Injected", "weight": 10.0,
        })
        assert resp.status_code == 404
