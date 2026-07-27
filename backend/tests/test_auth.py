"""Tests for auth endpoints: register, login, refresh, logout (cookie-based)."""

import asyncio

import pytest


# ── Registration ─────────────────────────────────────────────────────

async def test_register_success(client):
    resp = await client.post("/auth/register", json={
        "email": "new@example.com",
        "password": "securepass123",
        "full_name": "New User",
    })
    assert resp.status_code == 200
    assert resp.json() == {"detail": "ok"}
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies
    # Auth cookies must be HttpOnly
    set_cookie = ";".join(resp.headers.get_list("set-cookie")).lower()
    assert "httponly" in set_cookie


async def test_register_duplicate_email(client):
    payload = {
        "email": "dupe@example.com",
        "password": "securepass123",
        "full_name": "First User",
    }
    resp1 = await client.post("/auth/register", json=payload)
    assert resp1.status_code == 200

    resp2 = await client.post("/auth/register", json=payload)
    assert resp2.status_code == 400
    assert "already registered" in resp2.json()["detail"].lower()


# ── Login ────────────────────────────────────────────────────────────

async def test_login_success(client):
    await client.post("/auth/register", json={
        "email": "login@example.com",
        "password": "securepass123",
        "full_name": "Login User",
    })

    resp = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "securepass123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "wrong@example.com",
        "password": "securepass123",
        "full_name": "Wrong Pass User",
    })

    resp = await client.post("/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


# ── Token Refresh ────────────────────────────────────────────────────

async def test_refresh_token(client):
    reg = await client.post("/auth/register", json={
        "email": "refresh@example.com",
        "password": "securepass123",
        "full_name": "Refresh User",
    })
    old_refresh = reg.cookies["refresh_token"]

    # Wait so the new token gets a different exp claim
    await asyncio.sleep(1)

    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    # New refresh token should differ (rotation)
    assert resp.cookies["refresh_token"] != old_refresh

    # The old refresh token must no longer work (rotated out)
    client.cookies.set("refresh_token", old_refresh)
    resp2 = await client.post("/auth/refresh")
    assert resp2.status_code == 401


async def test_refresh_requires_refresh_type_token(client):
    """An access token must not be accepted as a refresh token."""
    reg = await client.post("/auth/register", json={
        "email": "typecheck@example.com",
        "password": "securepass123",
        "full_name": "Type Check",
    })
    access = reg.cookies["access_token"]
    client.cookies.set("refresh_token", access)
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


async def test_access_endpoint_rejects_refresh_token(client):
    """A refresh token must not be accepted as an access token."""
    reg = await client.post("/auth/register", json={
        "email": "typecheck2@example.com",
        "password": "securepass123",
        "full_name": "Type Check 2",
    })
    refresh = reg.cookies["refresh_token"]
    client.cookies.set("access_token", refresh)
    resp = await client.get("/users/me")
    assert resp.status_code == 401


# ── Logout ───────────────────────────────────────────────────────────

async def test_logout(client):
    reg = await client.post("/auth/register", json={
        "email": "logout@example.com",
        "password": "securepass123",
        "full_name": "Logout User",
    })
    refresh_before = reg.cookies["refresh_token"]

    resp = await client.post("/auth/logout")
    assert resp.status_code == 200

    # Refresh token should now be revoked
    client.cookies.set("refresh_token", refresh_before)
    resp2 = await client.post("/auth/refresh")
    assert resp2.status_code == 401
