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
