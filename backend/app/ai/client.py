import functools
import time
from threading import Lock

import anyio.to_thread
from groq import Groq
from app.config import settings

_client = None

PLACEHOLDER_KEYS = {"placeholder", "your-groq-key-here", ""}


class AIDisabledError(Exception):
    """Raised when the Groq API key is not configured."""

    def __init__(self):
        super().__init__(
            "AI features are disabled — add a real Groq API key to enable them"
        )


class AIUnavailableError(Exception):
    """Raised when the Groq API is temporarily unavailable (circuit open)."""

    def __init__(self):
        super().__init__(
            "AI features are temporarily unavailable. Please try again in a minute."
        )


class _CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = Lock()

    def is_open(self) -> bool:
        with self._lock:
            opened_at = self._opened_at
            if opened_at is None:
                return False
            if time.time() - opened_at >= self._recovery_timeout:
                self._failures = 0
                self._opened_at = None
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._failure_threshold:
                self._opened_at = time.time()


_breaker = _CircuitBreaker()


def is_ai_enabled() -> bool:
    return settings.GROQ_API_KEY not in PLACEHOLDER_KEYS


def get_groq_client() -> Groq:
    global _client
    if not is_ai_enabled():
        raise AIDisabledError()
    if _breaker.is_open():
        raise AIUnavailableError()
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


async def run_blocking(fn, *args, **kwargs):
    """Run a blocking call in a worker thread.

    The Groq SDK client is synchronous. Awaiting nothing and calling it straight
    from an ``async def`` handler pins the event loop for the whole round trip —
    seconds per call, and ``send_message`` makes up to ``MAX_TOOL_ROUNDS`` of
    them back to back, plus retry sleeps. On a worker serving every other
    request from that same loop, a handful of concurrent chat or document-parse
    requests is enough to stall the entire API: a denial of service any logged-in
    user can trigger by accident. Offloading keeps the loop free.

    ``anyio``'s default thread limiter (40) also caps how many model calls can be
    in flight per worker, which bounds memory during a traffic spike.
    """
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


async def acomplete(client: Groq, **kwargs):
    """Non-blocking ``client.chat.completions.create(...)``. See run_blocking."""
    return await run_blocking(client.chat.completions.create, **kwargs)


_STREAM_END = object()


async def aiter_stream(stream):
    """Iterate a blocking SDK stream as an async generator.

    ``for chunk in stream`` blocks inside ``next()`` waiting on the network for
    each token. Yielding to the loop *between* chunks (``await asyncio.sleep(0)``)
    does not help — the stall is inside the ``next()`` call itself, and it lasts
    for the whole generation. Pulling each chunk in a worker thread is what
    actually keeps the worker serving other requests while a plan streams.
    """
    iterator = iter(stream)
    while True:
        chunk = await run_blocking(next, iterator, _STREAM_END)
        if chunk is _STREAM_END:
            return
        yield chunk


def record_ai_success() -> None:
    _breaker.record_success()


def record_ai_failure() -> None:
    _breaker.record_failure()


# Keep old name as alias for any remaining references
get_gemini_client = get_groq_client
