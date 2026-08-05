"""Tests for the per-user DSA weekly-goal settings endpoints."""

import uuid

from httpx import ASGITransport, AsyncClient

from tests.conftest import CSRF_HEADERS

from app.services.auth import create_access_token, hash_password


async def _make_client(app, db):
    """Create a fresh user and return an authenticated client for them."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("testpass123"),
        full_name="DSA Test User",
        university="University of Toronto",
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
        headers=CSRF_HEADERS,
    )


# ── GET default ──────────────────────────────────────────────────────

async def test_get_settings_returns_default(auth_client):
    resp = await auth_client.get("/dsa/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["weekly_goal"] == 7
    assert data["is_default"] is True


# ── PUT round-trip ───────────────────────────────────────────────────

async def test_put_settings_round_trip(auth_client):
    put = await auth_client.put("/dsa/settings", json={"weekly_goal": 15})
    assert put.status_code == 200
    put_data = put.json()
    assert put_data["weekly_goal"] == 15
    assert put_data["is_default"] is False

    # A subsequent GET returns the stored value and is no longer a default.
    get = await auth_client.get("/dsa/settings")
    assert get.status_code == 200
    get_data = get.json()
    assert get_data["weekly_goal"] == 15
    assert get_data["is_default"] is False


async def test_put_settings_upsert_updates_existing(auth_client):
    await auth_client.put("/dsa/settings", json={"weekly_goal": 10})
    resp = await auth_client.put("/dsa/settings", json={"weekly_goal": 20})
    assert resp.status_code == 200
    assert resp.json()["weekly_goal"] == 20

    get = await auth_client.get("/dsa/settings")
    assert get.json()["weekly_goal"] == 20


# ── Validation ───────────────────────────────────────────────────────

async def test_put_settings_rejects_out_of_range(auth_client):
    too_low = await auth_client.put("/dsa/settings", json={"weekly_goal": 0})
    assert too_low.status_code == 422

    too_high = await auth_client.put("/dsa/settings", json={"weekly_goal": 101})
    assert too_high.status_code == 422


async def test_put_settings_boundaries_accepted(auth_client):
    low = await auth_client.put("/dsa/settings", json={"weekly_goal": 1})
    assert low.status_code == 200
    assert low.json()["weekly_goal"] == 1

    high = await auth_client.put("/dsa/settings", json={"weekly_goal": 100})
    assert high.status_code == 200
    assert high.json()["weekly_goal"] == 100


# ── Per-user isolation ───────────────────────────────────────────────

async def test_settings_isolated_per_user(auth_client, app, db):
    # First user sets their goal.
    await auth_client.put("/dsa/settings", json={"weekly_goal": 25})

    # A second user still sees the default and is unaffected.
    other = await _make_client(app, db)
    async with other as oc:
        get = await oc.get("/dsa/settings")
        assert get.json()["weekly_goal"] == 7
        assert get.json()["is_default"] is True

        await oc.put("/dsa/settings", json={"weekly_goal": 3})
        assert (await oc.get("/dsa/settings")).json()["weekly_goal"] == 3

    # First user's value is untouched by the second user's changes.
    assert (await auth_client.get("/dsa/settings")).json()["weekly_goal"] == 25


# ── Auth required ────────────────────────────────────────────────────

async def test_settings_requires_auth(client):
    assert (await client.get("/dsa/settings")).status_code == 401
    assert (await client.put("/dsa/settings", json={"weekly_goal": 5})).status_code == 401
