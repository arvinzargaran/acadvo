"""Tests for password reset, email verification, and account deletion re-auth."""

import re

import pytest


def _token_from(body: str) -> str:
    m = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert m, f"no token found in email body:\n{body}"
    return m.group(1)


# ── Email verification ───────────────────────────────────────────────

async def test_verification_email_sent_on_register(client, sent_emails):
    resp = await client.post("/auth/register", json={
        "accepted_terms": True,
        "email": "verify@example.com",
        "password": "securepass123",
        "full_name": "Verify User",
    })
    assert resp.status_code == 200
    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == "verify@example.com"
    assert "verify-email?token=" in sent_emails[0]["body"]


async def test_email_verification_flow(client, sent_emails):
    await client.post("/auth/register", json={
        "accepted_terms": True,
        "email": "verifyflow@example.com",
        "password": "securepass123",
        "full_name": "Verify Flow",
    })
    # user starts unverified
    me = await client.get("/users/me")
    assert me.json()["email_verified"] is False

    token = _token_from(sent_emails[-1]["body"])
    resp = await client.post("/auth/verify-email", json={"token": token})
    assert resp.status_code == 200

    me2 = await client.get("/users/me")
    assert me2.json()["email_verified"] is True

    # token is single-use
    reuse = await client.post("/auth/verify-email", json={"token": token})
    assert reuse.status_code == 400


async def test_verify_email_bad_token(client):
    resp = await client.post("/auth/verify-email", json={"token": "not-a-real-token"})
    assert resp.status_code == 400


# ── Password reset ───────────────────────────────────────────────────

async def test_forgot_password_no_enumeration(client, sent_emails):
    # Unknown email: still 200, but no email queued
    resp = await client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert resp.status_code == 200
    assert sent_emails == []


async def test_password_reset_flow(client, sent_emails):
    await client.post("/auth/register", json={
        "accepted_terms": True,
        "email": "resetflow@example.com",
        "password": "OldPassphrase123",
        "full_name": "Reset Flow",
    })
    sent_emails.clear()  # drop the verification email

    resp = await client.post("/auth/forgot-password", json={"email": "resetflow@example.com"})
    assert resp.status_code == 200
    assert len(sent_emails) == 1
    token = _token_from(sent_emails[-1]["body"])

    # Reset to a new password
    r = await client.post("/auth/reset-password", json={"token": token, "new_password": "NewPassphrase456"})
    assert r.status_code == 200

    # Old password no longer works, new one does
    old = await client.post("/auth/login", json={"email": "resetflow@example.com", "password": "OldPassphrase123"})
    assert old.status_code == 401
    new = await client.post("/auth/login", json={"email": "resetflow@example.com", "password": "NewPassphrase456"})
    assert new.status_code == 200

    # Token cannot be reused
    reuse = await client.post("/auth/reset-password", json={"token": token, "new_password": "AnotherPhrase789"})
    assert reuse.status_code == 400


async def test_reset_password_bad_token(client):
    resp = await client.post("/auth/reset-password", json={"token": "bogus", "new_password": "whateverPhrase12"})
    assert resp.status_code == 400


async def test_reset_password_too_short(client, sent_emails):
    await client.post("/auth/register", json={
        "accepted_terms": True,
        "email": "shortpw@example.com",
        "password": "OldPassphrase123",
        "full_name": "Short PW",
    })
    await client.post("/auth/forgot-password", json={"email": "shortpw@example.com"})
    token = _token_from(sent_emails[-1]["body"])
    resp = await client.post("/auth/reset-password", json={"token": token, "new_password": "short"})
    assert resp.status_code == 422  # pydantic min_length


# ── Account deletion re-auth ─────────────────────────────────────────

async def test_delete_account_requires_password(auth_client):
    # Wrong password is rejected
    wrong = await auth_client.request("DELETE", "/users/me", json={"password": "wrongpass"})
    assert wrong.status_code == 400

    # Still authenticated / account still exists
    me = await auth_client.get("/users/me")
    assert me.status_code == 200


async def test_delete_account_missing_body(auth_client):
    resp = await auth_client.request("DELETE", "/users/me")
    assert resp.status_code == 422


async def test_delete_account_success(auth_client):
    resp = await auth_client.request("DELETE", "/users/me", json={"password": "testpass123"})
    assert resp.status_code == 204
    # Account is gone
    me = await auth_client.get("/users/me")
    assert me.status_code == 401
