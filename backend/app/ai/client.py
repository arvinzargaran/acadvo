import time
from threading import Lock

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


def record_ai_success() -> None:
    _breaker.record_success()


def record_ai_failure() -> None:
    _breaker.record_failure()


# Keep old name as alias for any remaining references
get_gemini_client = get_groq_client
