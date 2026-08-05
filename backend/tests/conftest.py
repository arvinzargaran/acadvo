"""
Test configuration — async SQLite in-memory database with full fixture suite.

Handles PostgreSQL → SQLite type compatibility (UUID, JSONB, Numeric, CheckConstraint).
"""

import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-32chars!")

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models import *  # noqa: F401, F403 — ensure all models registered with Base
from app.services.auth import create_access_token, hash_password

# Rate limits are process-global and persist across tests; disable enforcement so
# test volume doesn't trip limits. Rate-limit behaviour is verified separately.
limiter.enabled = False


# ---------------------------------------------------------------------------
# SQLite-compatible engine
# ---------------------------------------------------------------------------

# Use a single shared in-memory database across connections (via naming)
TEST_DATABASE_URL = "sqlite+aiosqlite:///file:test.db?mode=memory&cache=shared&uri=true"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_fks(dbapi_conn, connection_record):
    """Enable foreign key enforcement in SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------------------------------------------------------------------------
# Patch PostgreSQL types for SQLite at import time
# ---------------------------------------------------------------------------

from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy import String, Text, DateTime as SA_DateTime
from sqlalchemy.ext.compiler import compiles


@compiles(PG_UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_tz_handling(dbapi_conn, connection_record):
    """Patch SQLite to return timezone-aware datetimes."""
    pass


# Monkey-patch the RefreshToken model's expires_at to handle naive datetimes.
# SQLite doesn't store timezone info, so we ensure comparisons work.
import app.services.auth as _auth_mod
_orig_refresh = _auth_mod.refresh_access_token

async def _patched_refresh(refresh_token, db):
    """Wrapper that makes expires_at timezone-aware before comparison."""
    from sqlalchemy import select as sel
    from app.models.user import RefreshToken as RT

    result = await db.execute(sel(RT).where(RT.token == _auth_mod._hash_token(refresh_token)))
    db_token = result.scalar_one_or_none()
    if db_token and db_token.expires_at and db_token.expires_at.tzinfo is None:
        db_token.expires_at = db_token.expires_at.replace(tzinfo=timezone.utc)

    # Now call the original (it will re-fetch but the object is cached in session)
    return await _orig_refresh(refresh_token, db)

_auth_mod.refresh_access_token = _patched_refresh


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    """Yield a test database session."""
    async with TestingSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# App + client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def app():
    """Return the FastAPI app with test DB override."""
    from app.main import app as _app

    async def _test_get_db():
        async with TestingSessionLocal() as session:
            yield session

    _app.dependency_overrides[get_db] = _test_get_db
    yield _app
    _app.dependency_overrides.clear()


# The CSRF middleware requires this header on every state-changing request, the
# same way the real SPA sends it. Tests that specifically exercise the CSRF
# rejection path build their own client without it.
CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture
async def client(app):
    """Unauthenticated async HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=CSRF_HEADERS
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_user(db):
    """Create and return a test user in the database.

    Verified, because that is the ordinary state of an account in use — the AI
    routers refuse unverified accounts (see deps.require_verified_email). Use
    `unverified_user` to exercise that gate.
    """
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Test User",
        university="University of Toronto",
        program="Computer Science",
        start_year=2023,
        expected_graduation_year=2027,
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def unverified_user(db):
    """A signed-up account that has not yet confirmed its email address."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="unverified@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Unverified User",
        university="University of Toronto",
        program="Computer Science",
        email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def unverified_client(app, unverified_user):
    """Authenticated client whose account has an unverified email."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": create_access_token(unverified_user.id)},
        headers=CSRF_HEADERS,
    ) as c:
        yield c


@pytest.fixture
async def auth_token(test_user):
    """Return a valid JWT access token for the test user."""
    return create_access_token(test_user.id)


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture outgoing emails (the auth router imports send_email directly)."""
    box = []

    async def _fake_send(to, subject, body):
        box.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("app.routers.auth.send_email", _fake_send)
    return box


@pytest.fixture
async def auth_client(app, test_user, auth_token):
    """Authenticated async HTTP client (auth is cookie-based)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": auth_token},
        headers=CSRF_HEADERS,
    ) as c:
        yield c
