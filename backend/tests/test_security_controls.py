"""Regression tests for the security controls added in the hardening pass.

Each of these guards a control that is invisible in normal use and therefore
easy to delete by accident: nothing in the product breaks if CSRF checking or
path scrubbing quietly stops working.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.observability import scrub_path
from app.services.auth import (
    LOGIN_ATTEMPTS_BEFORE_THROTTLE,
    create_refresh_token,
    hash_password,
)
from tests.conftest import CSRF_HEADERS


# ── CSRF ─────────────────────────────────────────────────────────────

@pytest.fixture
async def no_csrf_client(app, test_user):
    """Authenticated client that does NOT send the CSRF header."""
    from app.services.auth import create_access_token

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": create_access_token(test_user.id)},
    ) as c:
        yield c


async def test_state_changing_request_without_csrf_header_is_rejected(no_csrf_client):
    resp = await no_csrf_client.post("/degree/courses", json={
        "course_code": "CSC148",
        "course_name": "Intro",
        "credit_value": 3.0,
    })
    assert resp.status_code == 403
    assert "X-Requested-With" in resp.json()["detail"]


async def test_delete_without_csrf_header_is_rejected(no_csrf_client):
    resp = await no_csrf_client.request(
        "DELETE", "/users/me", json={"password": "testpass123"}
    )
    assert resp.status_code == 403


async def test_safe_methods_do_not_require_csrf_header(no_csrf_client):
    """A GET must still work — the check only applies to state changes."""
    resp = await no_csrf_client.get("/users/me")
    assert resp.status_code == 200


async def test_csrf_header_allows_the_request(auth_client):
    resp = await auth_client.get("/users/me")
    assert resp.status_code == 200
    resp = await auth_client.put("/users/me", json={"city": "Toronto"})
    assert resp.status_code == 200


# ── Password policy ──────────────────────────────────────────────────

@pytest.mark.parametrize(
    "password",
    [
        "short",                 # under the length floor
        "elevenchars",           # 11 chars, still under 12
        "password123",           # in the breach blocklist
        "aaaaaaaaaaaaaaaa",      # long but almost no entropy
        "x" * 100,               # past bcrypt's 72-byte limit
    ],
)
async def test_register_rejects_weak_password(client, password):
    resp = await client.post("/auth/register", json={
        "email": f"weak-{uuid.uuid4().hex[:8]}@example.com",
        "password": password,
        "full_name": "Weak Password",
    })
    assert resp.status_code == 422


async def test_register_accepts_a_reasonable_passphrase(client):
    resp = await client.post("/auth/register", json={
        "email": "strongpw@example.com",
        "password": "correct horse battery staple",
        "full_name": "Strong Password",
    })
    assert resp.status_code == 200


# ── Login throttling ─────────────────────────────────────────────────

async def test_repeated_failures_throttle_the_account(client, db):
    from app.models.user import User

    email = "throttle@example.com"
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("correct horse battery staple"),
        full_name="Throttle Me",
    )
    db.add(user)
    await db.commit()

    for _ in range(LOGIN_ATTEMPTS_BEFORE_THROTTLE):
        resp = await client.post(
            "/auth/login", json={"email": email, "password": "wrong guess here"}
        )
        assert resp.status_code == 401

    # The correct password is now refused too — the account is throttled.
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert resp.status_code == 401

    await db.refresh(user)
    assert user.failed_login_attempts >= LOGIN_ATTEMPTS_BEFORE_THROTTLE
    assert user.login_locked_until is not None

    # A throttled account must not be distinguishable from a wrong password.
    assert resp.json()["detail"] == "Invalid email or password"


async def test_successful_login_clears_the_failure_counter(client, db):
    from app.models.user import User

    email = "clears@example.com"
    password = "correct horse battery staple"
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password(password),
        full_name="Clears Counter",
        failed_login_attempts=2,
    )
    db.add(user)
    await db.commit()

    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200

    await db.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.login_locked_until is None


# ── Refresh-token reuse detection ────────────────────────────────────

async def test_replaying_a_used_refresh_token_revokes_the_whole_family(client, db, test_user):
    """A stolen refresh token must not buy a session that outlives detection."""
    from app.models.user import RefreshToken
    from sqlalchemy import select

    first = await create_refresh_token(test_user.id, db)
    second = await create_refresh_token(test_user.id, db)

    # Redeem the first token — it is now consumed and rotated.
    client.cookies.set("refresh_token", first)
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200

    # Replay it. This is the signal that someone else has a copy.
    client.cookies.set("refresh_token", first)
    replay = await client.post("/auth/refresh")
    assert replay.status_code == 401

    # Every outstanding token for this user is gone, including the rotated one
    # the legitimate session just received and the unrelated `second`.
    rows = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.user_id == test_user.id)
        )
    ).scalars().all()
    assert rows == []

    client.cookies.set("refresh_token", second)
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_garbage_refresh_token_does_not_revoke_anyone(client, db, test_user):
    """Reuse detection must not become a way to log other users out."""
    from app.models.user import RefreshToken
    from sqlalchemy import select

    valid = await create_refresh_token(test_user.id, db)

    client.cookies.set("refresh_token", "not-a-real-token")
    assert (await client.post("/auth/refresh")).status_code == 401

    rows = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.user_id == test_user.id)
        )
    ).scalars().all()
    assert len(rows) == 1

    client.cookies.set("refresh_token", valid)
    assert (await client.post("/auth/refresh")).status_code == 200


# ── JWT handling ─────────────────────────────────────────────────────

async def test_token_without_expiry_is_rejected(client, test_user):
    """`exp` is required, so a never-expiring forged token is refused."""
    token = jwt.encode(
        {"sub": str(test_user.id), "type": "access"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    client.cookies.set("access_token", token)
    assert (await client.get("/users/me")).status_code == 401


async def test_alg_none_token_is_rejected(client, test_user):
    """The classic algorithm-confusion forgery must not authenticate."""
    unsigned = jwt.encode(
        {
            "sub": str(test_user.id),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        key="",
        algorithm="none",
    )
    client.cookies.set("access_token", unsigned)
    assert (await client.get("/users/me")).status_code == 401


async def test_config_rejects_a_non_hmac_jwt_algorithm():
    from app.config import Settings

    with pytest.raises(ValueError):
        Settings(JWT_SECRET_KEY="x" * 32, JWT_ALGORITHM="none")
    with pytest.raises(ValueError):
        Settings(JWT_SECRET_KEY="x" * 32, JWT_ALGORITHM="RS256")


# ── Secret scrubbing in logs ─────────────────────────────────────────

def test_calendar_feed_token_is_scrubbed_from_log_paths():
    raw = "/calendar/feed/AbCdEf-secret-token-1234.ics"
    assert scrub_path(raw) == "/calendar/feed/<redacted>.ics"
    assert "secret-token" not in scrub_path(raw)


def test_scrub_path_leaves_ordinary_paths_alone():
    assert scrub_path("/degree/courses") == "/degree/courses"
    assert scrub_path("/users/me") == "/users/me"


# ── Cookie flags ─────────────────────────────────────────────────────

async def test_auth_cookies_are_httponly_and_scoped(client):
    resp = await client.post("/auth/register", json={
        "email": "cookieflags@example.com",
        "password": "correct horse battery staple",
        "full_name": "Cookie Flags",
    })
    assert resp.status_code == 200

    cookies = {}
    for header in resp.headers.get_list("set-cookie"):
        name = header.split("=", 1)[0]
        cookies[name] = header.lower()

    assert "httponly" in cookies["access_token"]
    assert "httponly" in cookies["refresh_token"]
    # The refresh cookie only goes to the endpoints that redeem it, so it is not
    # attached to every ordinary API call.
    assert "path=/auth" in cookies["refresh_token"]


# ── Upload validation ────────────────────────────────────────────────

def test_sniffing_rejects_a_mislabelled_file():
    """A declared type that the bytes contradict must be refused."""
    from fastapi import HTTPException

    from app.routers.degree import ALLOWED_MIME_TYPES
    from app.services.uploads import validate_upload

    # An ELF binary claiming to be a PNG.
    with pytest.raises(HTTPException) as exc:
        validate_upload(b"\x7fELF\x02\x01\x01" + b"\x00" * 64, "image/png", ALLOWED_MIME_TYPES)
    assert exc.value.status_code == 400
    assert "do not match" in exc.value.detail

    # A PDF renamed to .xlsx — real type, wrong declaration.
    with pytest.raises(HTTPException):
        validate_upload(b"%PDF-1.7\n%test", "application/vnd.ms-excel", ALLOWED_MIME_TYPES)


def test_sniffing_accepts_matching_bytes():
    from app.routers.degree import ALLOWED_MIME_TYPES
    from app.services.uploads import validate_upload

    assert validate_upload(b"%PDF-1.7\n%x", "application/pdf", ALLOWED_MIME_TYPES) == "application/pdf"
    assert validate_upload(b"\x89PNG\r\n\x1a\nrest", "image/png", ALLOWED_MIME_TYPES) == "image/png"
    # Browsers send the non-standard image/jpg; it must map to real JPEG bytes.
    assert validate_upload(b"\xff\xd8\xff\xe0junk", "image/jpg", ALLOWED_MIME_TYPES) == "image/jpeg"


def test_csv_must_be_text_not_a_disguised_binary():
    from fastapi import HTTPException

    from app.routers.degree import ALLOWED_MIME_TYPES
    from app.services.uploads import validate_upload

    assert validate_upload(b"code,name\nCSC148,Intro\n", "text/csv", ALLOWED_MIME_TYPES) == "text/csv"
    with pytest.raises(HTTPException):
        validate_upload(b"PK\x03\x04binary", "text/csv", ALLOWED_MIME_TYPES)


def test_disallowed_and_empty_uploads_are_rejected():
    from fastapi import HTTPException

    from app.routers.degree import ALLOWED_MIME_TYPES
    from app.services.uploads import validate_upload

    with pytest.raises(HTTPException) as exc:
        validate_upload(b"MZ\x90\x00", "application/x-msdownload", ALLOWED_MIME_TYPES)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException):
        validate_upload(b"", "application/pdf", ALLOWED_MIME_TYPES)


def test_spreadsheet_extraction_is_bounded():
    """A file well inside the byte limit must not expand without bound."""
    import io

    import openpyxl

    from app.services.uploads import (
        MAX_EXTRACTED_CHARS,
        MAX_SPREADSHEET_ROWS,
        spreadsheet_to_text,
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(MAX_SPREADSHEET_ROWS + 500):
        ws.append(["x" * 40, "y" * 40, "z" * 40])
    buf = io.BytesIO()
    wb.save(buf)

    text = spreadsheet_to_text(
        buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert len(text) <= MAX_EXTRACTED_CHARS + 50
    assert "truncated" in text


def test_csv_extraction_is_capped():
    from app.services.uploads import MAX_EXTRACTED_CHARS, spreadsheet_to_text

    huge = ("a,b,c\n" * 200_000).encode()
    assert len(spreadsheet_to_text(huge, "text/csv")) <= MAX_EXTRACTED_CHARS


def test_uvicorn_access_log_path_is_scrubbed():
    """The middleware and uvicorn log independently; both must redact.

    uvicorn's access logger never passes through our request middleware, so
    without its own filter the feed token still lands in the log line right
    next to the redacted one.
    """
    import logging

    from app.observability import ScrubAccessLogFilter

    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:1234", "GET", "/calendar/feed/SECRETTOKEN.ics", "1.1", 200),
        exc_info=None,
    )
    ScrubAccessLogFilter().filter(record)

    assert "SECRETTOKEN" not in record.getMessage()
    assert "<redacted>" in record.getMessage()


def test_access_log_filter_leaves_other_records_alone():
    import logging

    from app.observability import ScrubAccessLogFilter

    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:1234", "GET", "/degree/courses", "1.1", 200),
        exc_info=None,
    )
    ScrubAccessLogFilter().filter(record)
    assert "/degree/courses" in record.getMessage()

    # A record with an unexpected shape must pass through untouched, not crash.
    other = logging.LogRecord(
        name="uvicorn.access", level=logging.INFO, pathname=__file__, lineno=1,
        msg="something else", args=None, exc_info=None,
    )
    assert ScrubAccessLogFilter().filter(other) is True


async def test_csrf_rejection_still_carries_cors_headers(no_csrf_client):
    """A blocked request must still be *readable* by the browser.

    CORS middleware has to wrap the CSRF check. If it sits inside, the 403
    short-circuits before CORS runs, the response has no
    Access-Control-Allow-Origin, and the browser reports an opaque
    "Failed to fetch" instead of the status — the request is blocked either way,
    but the SPA can't show an error and nobody can debug it.
    """
    origin = settings.CORS_ORIGINS.split(",")[0].strip()
    resp = await no_csrf_client.post(
        "/degree/courses",
        json={"course_code": "CSC148", "course_name": "Intro", "credit_value": 3.0},
        headers={"Origin": origin},
    )
    assert resp.status_code == 403
    assert resp.headers.get("access-control-allow-origin") == origin


async def test_preflight_is_not_blocked_by_csrf(client):
    """The browser's own OPTIONS preflight must pass through untouched."""
    origin = settings.CORS_ORIGINS.split(",")[0].strip()
    resp = await client.options(
        "/degree/courses",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-requested-with",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin
    assert "x-requested-with" in resp.headers.get("access-control-allow-headers", "").lower()


# ── Email verification gate ──────────────────────────────────────────

async def test_unverified_account_cannot_use_the_ai_advisor(unverified_client):
    """AI calls cost money per request; an unconfirmed address must not spend it."""
    resp = await unverified_client.post("/conversations", json={"title": "Hi"})
    assert resp.status_code == 403
    assert "Verify your email" in resp.json()["detail"]
    assert "AI advisor" in resp.json()["detail"]


async def test_unverified_account_cannot_generate_a_plan(unverified_client):
    resp = await unverified_client.post("/course-advisor/generate-plan", json={})
    assert resp.status_code == 403


async def test_unverified_account_cannot_parse_a_document(unverified_client):
    files = {"file": ("x.pdf", b"%PDF-1.7 test", "application/pdf")}
    resp = await unverified_client.post("/degree/parse-document", files=files)
    assert resp.status_code == 403


async def test_unverified_account_cannot_review_a_resume(unverified_client):
    files = {"file": ("x.pdf", b"%PDF-1.7 test", "application/pdf")}
    resp = await unverified_client.post("/career/review-resume", files=files)
    assert resp.status_code == 403


async def test_unverified_account_can_still_complete_onboarding(unverified_client):
    """The gate must not lock new users out of signup.

    Onboarding is built entirely from these calls. Gating them would turn a
    security control into a product outage for every new account.
    """
    assert (await unverified_client.put("/users/me", json={"city": "Toronto"})).status_code == 200

    req = await unverified_client.post(
        "/degree/requirements", json={"bucket_name": "Major", "credits_required": 60}
    )
    assert req.status_code == 201

    course = await unverified_client.post("/degree/courses", json={
        "course_code": "CSC148", "course_name": "Intro", "credit_value": 3.0,
    })
    assert course.status_code == 201

    proj = await unverified_client.post(
        "/projects", json={"name": "Portfolio", "priority": 1}
    )
    assert proj.status_code == 201

    target = await unverified_client.post(
        "/career/targets", json={"company_name": "Shopify", "status": "researching"}
    )
    assert target.status_code == 201

    done = await unverified_client.put("/users/me", json={"onboarding_complete": True})
    assert done.status_code == 200


async def test_unverified_account_can_read_and_manage_its_own_account(unverified_client):
    """Reads and account management stay open — locking someone out of their
    own settings is not a security win."""
    assert (await unverified_client.get("/users/me")).status_code == 200
    assert (await unverified_client.get("/degree/courses")).status_code == 200
    assert (await unverified_client.get("/conversations")).status_code == 200

    changed = await unverified_client.post("/users/me/password", json={
        "current_password": "testpass123",
        "new_password": "correct horse battery staple",
    })
    assert changed.status_code == 204


async def test_verified_account_passes_the_gate(auth_client):
    """The gate must not block a normal verified account.

    A 403 here would mean the gate is on; anything else (including a 5xx from
    the AI being unconfigured in tests) means it let the request through.
    """
    resp = await auth_client.post("/conversations", json={"title": "Hi"})
    assert resp.status_code != 403


async def test_verifying_email_immediately_lifts_the_gate(client, db, unverified_user, sent_emails):
    """No waiting for the access token to expire — the flag is read per request."""
    import re

    from app.services.auth import create_access_token

    client.cookies.set("access_token", create_access_token(unverified_user.id))
    assert (await client.post("/conversations", json={"title": "Hi"})).status_code == 403

    # Walk the real flow: request a link, then consume the token from the email.
    sent_emails.clear()
    assert (await client.post("/auth/resend-verification")).status_code == 200
    token = re.search(r"verify-email\?token=([\w\-]+)", sent_emails[-1]["body"]).group(1)
    assert (await client.post("/auth/verify-email", json={"token": token})).status_code == 200

    # Same cookie, same token — the gate is lifted because the flag is re-read.
    assert (await client.post("/conversations", json={"title": "Hi"})).status_code != 403
