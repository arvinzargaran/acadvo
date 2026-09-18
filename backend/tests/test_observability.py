"""Tests for observability: request-id middleware and JSON formatter."""

import json
import logging

from app.observability import JsonFormatter, request_id_var


# ── Request-id middleware ────────────────────────────────────────────

async def test_request_id_generated_on_response(client):
    """Every response carries an X-Request-ID header even if none was sent."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")


async def test_request_id_propagated_from_header(client):
    """An incoming X-Request-ID is echoed back unchanged."""
    incoming = "test-request-id-123"
    resp = await client.get("/health", headers={"X-Request-ID": incoming})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == incoming


# ── JSON formatter ───────────────────────────────────────────────────

def test_json_formatter_shape_and_extras():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="acadvo.ai",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="tool executed",
        args=(),
        exc_info=None,
    )
    # Simulate an "extra" and the request-id filter.
    record.tool = "get_degree_summary"
    record.request_id = "abc123"

    payload = json.loads(formatter.format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "acadvo.ai"
    assert payload["message"] == "tool executed"
    assert payload["request_id"] == "abc123"
    assert payload["tool"] == "get_degree_summary"
    assert "timestamp" in payload


def test_json_formatter_defaults_request_id_when_absent():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="acadvo",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg="no context",
        args=(),
        exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert payload["request_id"] == "-"


# ── Readiness, quota, and the things an operator watches ─────────────


def _break_the_database(message="connection refused"):
    """Override the app's DB dependency with a session whose queries fail.

    Overriding the dependency rather than patching a module global is what makes
    this a real test of the endpoint: it exercises the same seam the app uses to
    get a session, so a refactor that changes where the session comes from does
    not quietly stop this from testing anything.
    """
    from app.database import get_db
    from app.main import app as fastapi_app

    class _BrokenSession:
        async def execute(self, *a, **kw):
            raise RuntimeError(message)

    async def _override():
        yield _BrokenSession()

    previous = fastapi_app.dependency_overrides.get(get_db)
    fastapi_app.dependency_overrides[get_db] = _override
    return get_db, previous


def _restore_database(get_db, previous):
    from app.main import app as fastapi_app

    if previous is None:
        fastapi_app.dependency_overrides.pop(get_db, None)
    else:
        fastapi_app.dependency_overrides[get_db] = previous


async def test_liveness_stays_up_without_the_database(client):
    """Liveness answers "should this container be restarted", and restarting the
    API because Postgres blipped replaces one broken dependency with two."""
    get_db, previous = _break_the_database()
    try:
        resp = await client.get("/health")
    finally:
        _restore_database(get_db, previous)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_readiness_reports_ok_when_the_database_answers(client):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


async def test_readiness_fails_closed_when_the_database_is_unreachable(client):
    """The defect this endpoint exists for: `/health` returns 200 the instant
    uvicorn binds, so a container with wrong credentials reports healthy, the
    startup gate opens, and an uptime monitor stays green while every request
    500s."""
    get_db, previous = _break_the_database()
    try:
        resp = await client.get("/health/ready")
    finally:
        _restore_database(get_db, previous)
    assert resp.status_code == 503
    assert resp.json()["checks"]["database"] == "unavailable"


async def test_readiness_never_leaks_the_connection_error(client):
    """This endpoint is unauthenticated and a driver error names hosts, ports
    and usernames."""
    get_db, previous = _break_the_database(
        "could not connect to postgres://acadvo:hunter2@db:5432"
    )
    try:
        body = (await client.get("/health/ready")).text
    finally:
        _restore_database(get_db, previous)
    assert "hunter2" not in body
    assert "5432" not in body


def test_quota_headers_are_recorded_from_a_response():
    from app.ai.client import quota_snapshot, record_quota

    record_quota(
        {
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-remaining-requests": "997",
            "x-ratelimit-limit-tokens": "8000",
            "x-ratelimit-remaining-tokens": "7907",
            "x-ratelimit-reset-requests": "1m26.4s",
        },
        model="openai/gpt-oss-120b",
    )
    snap = quota_snapshot()
    assert snap["remaining_requests"] == 997
    assert snap["limit_tokens"] == 8000
    assert snap["model"] == "openai/gpt-oss-120b"


def test_a_low_request_allowance_is_warned_about(caplog):
    """On a free tier the daily request budget runs out mid-afternoon and every
    AI feature fails at once. Nothing else in the system reports why."""
    import logging

    from app.ai.client import record_quota

    records = []

    class _Collect(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("acadvo.ai.client")
    handler = _Collect(level=logging.WARNING)
    logger.addHandler(handler)
    try:
        record_quota(
            {
                "x-ratelimit-limit-requests": "1000",
                "x-ratelimit-remaining-requests": "12",
                "x-ratelimit-reset-requests": "41m",
            },
            model="openai/gpt-oss-120b",
        )
    finally:
        logger.removeHandler(handler)

    assert any("quota low" in m and "41m" in m for m in records)


def test_healthy_quota_is_not_warned_about():
    import logging

    from app.ai.client import record_quota

    records = []

    class _Collect(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("acadvo.ai.client")
    handler = _Collect(level=logging.WARNING)
    logger.addHandler(handler)
    try:
        record_quota(
            {
                "x-ratelimit-limit-requests": "1000",
                "x-ratelimit-remaining-requests": "900",
            },
            model="m",
        )
    finally:
        logger.removeHandler(handler)

    assert not any("quota low" in m for m in records)


def test_malformed_quota_headers_are_ignored_not_raised():
    """Quota bookkeeping must never fail a request the provider already
    answered successfully."""
    from app.ai.client import record_quota

    record_quota({"x-ratelimit-limit-requests": "not-a-number"}, model="m")
    record_quota({}, model="m")


async def test_quota_is_recorded_through_the_raw_response_path():
    """The production path. If this silently stopped working, the quota warning
    would never fire again and nothing would report its own absence."""
    import types

    from app.ai.client import acomplete, quota_snapshot

    completion = types.SimpleNamespace(choices=[])

    class _Raw:
        headers = {
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-remaining-requests": "42",
        }

        def parse(self):
            return completion

    completions = types.SimpleNamespace(
        with_raw_response=types.SimpleNamespace(create=lambda **kw: _Raw()),
        create=lambda **kw: (_ for _ in ()).throw(
            AssertionError("must not bypass the raw-response path")
        ),
    )
    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=completions))

    result = await acomplete(client, model="openai/gpt-oss-120b", messages=[])
    assert result is completion
    assert quota_snapshot()["remaining_requests"] == 42


async def test_a_client_without_raw_responses_still_works():
    """Quota capture is telemetry: it must never decide whether a request can be
    made, and it must not force every stand-in client to grow an SDK surface it
    does not use."""
    import types

    from app.ai.client import acomplete

    completion = types.SimpleNamespace(choices=[])
    completions = types.SimpleNamespace(create=lambda **kw: completion)
    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=completions))

    assert await acomplete(client, model="m", messages=[]) is completion
