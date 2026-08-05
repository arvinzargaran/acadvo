"""Structured (JSON) logging, request-id propagation, and optional Sentry.

All three are env-gated and cheap when unused:

* JSON logging is attached only to the ``acadvo`` logger namespace, so it does
  not disturb uvicorn's access/error loggers or the existing ``app`` logger.
* The request-id middleware assigns/propagates ``X-Request-ID`` and stashes it
  in a :class:`contextvars.ContextVar` so every ``acadvo.*`` log record carries
  the id without threading it through call signatures.
* Sentry only initialises when ``SENTRY_DSN`` is set; the SDK is imported
  lazily so a missing package never blocks startup.

JSON log record schema (top-level keys):
    timestamp        ISO-8601 UTC, e.g. "2026-07-17T12:00:00.123456+00:00"
    level            log level name (INFO, DEBUG, WARNING, ERROR, ...)
    logger           logger name (e.g. "acadvo.ai", "acadvo.request")
    message          the formatted log message
    request_id       current request id, or "-" when outside a request
    exception        multi-line traceback string (only when exc_info is set)
    ...extras        any keyword passed via ``logger.x(..., extra={...})``
                     is merged in as an additional top-level key
"""

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from app.config import settings

# ---------------------------------------------------------------------------
# Request-id context
# ---------------------------------------------------------------------------

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str:
    """Return the current request id, or ``"-"`` when outside a request."""
    return request_id_var.get() or "-"


# Standard attributes present on every LogRecord; everything else in
# ``record.__dict__`` is treated as caller-supplied ``extra`` and promoted to a
# top-level JSON field.
_RESERVED_LOG_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or "-",
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        # Promote caller-supplied extras (never overwrite the reserved keys).
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS or key in payload:
                continue
            if key.startswith("_") or key == "request_id":
                continue
            payload[key] = value

        return json.dumps(payload, default=str)


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every record the handler sees."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class ScrubAccessLogFilter(logging.Filter):
    """Redact secret-bearing paths from uvicorn's access log.

    Our own request middleware scrubs the path it logs, but uvicorn writes an
    independent access line through the ``uvicorn.access`` logger, which never
    passes through that middleware. Without this filter the calendar feed token
    is still emitted in full on every poll — the redaction would look like it
    worked while the credential kept leaking from the line next to it.

    uvicorn formats access records as
    ``'%s - "%s %s HTTP/%s" %d'`` with args
    ``(client_addr, method, full_path, http_version, status_code)``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str):
            scrubbed = scrub_path(args[2])
            if scrubbed != args[2]:
                record.args = (args[0], args[1], scrubbed, args[3], args[4])
        return True


def configure_logging() -> None:
    """Attach the JSON handler to the ``acadvo`` logger namespace (idempotent)."""
    # Applied regardless of the guard below: uvicorn installs its access logger
    # after import, and this must be attached whenever the app is configured.
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, ScrubAccessLogFilter) for f in access_logger.filters):
        access_logger.addFilter(ScrubAccessLogFilter())

    logger = logging.getLogger("acadvo")
    if getattr(logger, "_acadvo_configured", False):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    # Isolated namespace: do not double-emit through the root logger.
    logger.propagate = False
    logger._acadvo_configured = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Request-id middleware
# ---------------------------------------------------------------------------

REQUEST_ID_HEADER = "X-Request-ID"
_request_logger = logging.getLogger("acadvo.request")

# Paths whose URL *is* a secret. /calendar/feed/{token}.ics authenticates with
# the token in the path, and calendar clients re-poll it every few hours — so
# logging the raw path would sprinkle a permanent, non-expiring credential for
# a user's full academic schedule through the application logs, any log
# aggregator, and every Sentry breadcrumb.
_SECRET_PATH_PATTERNS = (
    (re.compile(r"^/calendar/feed/[^/]+\.ics$"), "/calendar/feed/<redacted>.ics"),
)


def scrub_path(path: str) -> str:
    """Replace secret-bearing URL path segments with a placeholder."""
    for pattern, replacement in _SECRET_PATH_PATTERNS:
        if pattern.match(path):
            return replacement
    return path


def install_request_id_middleware(app) -> None:
    """Register the request-id / request-logging middleware on ``app``.

    Call this LAST so the middleware sits outermost and wraps CORS, security
    headers, rate limiting, and routing — giving an accurate end-to-end
    duration and ensuring the id is set for the whole request lifecycle.
    """

    @app.middleware("http")
    async def request_id_middleware(request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        rid = incoming or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            response.headers[REQUEST_ID_HEADER] = rid
            _request_logger.info(
                "request completed",
                extra={
                    "http_method": request.method,
                    "path": scrub_path(request.url.path),
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            _request_logger.exception(
                "request failed",
                extra={
                    "http_method": request.method,
                    "path": scrub_path(request.url.path),
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_var.reset(token)


# ---------------------------------------------------------------------------
# Sentry (optional)
# ---------------------------------------------------------------------------

_sentry_logger = logging.getLogger("acadvo.sentry")


def init_sentry() -> bool:
    """Initialise Sentry when ``SENTRY_DSN`` is set. Returns True if enabled.

    No-ops (returns False) when the DSN is empty. If the DSN is set but
    ``sentry-sdk`` is not importable, it logs a warning and continues — Sentry
    must never be required for the app to boot.
    """
    if not settings.SENTRY_DSN:
        return False

    try:
        import sentry_sdk
    except ImportError:
        _sentry_logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; error tracking disabled"
        )
        return False

    def _scrub_event(event, hint):
        """Redact secret-bearing URLs before anything leaves the process.

        Sentry attaches the full request URL to every event. For the calendar
        feed that URL is the credential itself, so without this an error report
        hands a third-party service permanent read access to a user's schedule.
        """
        request = event.get("request")
        if isinstance(request, dict) and isinstance(request.get("url"), str):
            url = request["url"]
            scheme, _, rest = url.partition("://")
            host, slash, path = rest.partition("/")
            scrubbed = scrub_path(f"{slash}{path}")
            if scrubbed != f"{slash}{path}":
                request["url"] = f"{scheme}://{host}{scrubbed}"
        return event

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        before_send=_scrub_event,
    )
    _sentry_logger.info(
        "sentry initialised",
        extra={"traces_sample_rate": settings.SENTRY_TRACES_SAMPLE_RATE},
    )
    return True
