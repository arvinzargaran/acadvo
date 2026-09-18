import functools
import logging
import re
import time
from threading import Lock

import anyio.to_thread
from groq import APIConnectionError, APIStatusError, Groq
from app.config import settings

logger = logging.getLogger("acadvo.ai.client")

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


# Errors that mean "the AI provider said no", as opposed to "this code is
# wrong". Routers with a blanket `except Exception` that turns any failure into
# a generic 422 must re-raise these first: the app-level handlers in main.py
# know how to phrase them (unconfigured key, provider outage, request over the
# account's token-per-minute cap), and flattening them loses the one piece of
# information the user or the operator could act on.
AI_PROVIDER_ERRORS = (
    AIDisabledError,
    AIUnavailableError,
    APIStatusError,
    APIConnectionError,
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
        # Bounded on purpose — see GROQ_TIMEOUT_SECONDS in config.py. Left at
        # the SDK defaults, one model call can occupy a worker thread for
        # minutes, and the pool is what every other request is waiting on.
        _client = Groq(
            api_key=settings.GROQ_API_KEY,
            timeout=settings.GROQ_TIMEOUT_SECONDS,
            max_retries=settings.GROQ_SDK_MAX_RETRIES,
        )
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


# ── Provider quota, observed rather than guessed ─────────────────────
#
# Groq reports the account's remaining allowance on the headers of every
# response, and until now the app threw them away. That is the one number an
# operator needs and cannot get any other way: on a free tier the daily request
# allowance runs out mid-afternoon, every AI feature starts failing at once, and
# the logs show a pile of provider errors with no indication that the cause is a
# quota that resets on its own. Reading the headers turns "the AI is broken" into
# "the AI is rate-limited until 14:32", which is a different operational
# response.
#
# Deliberately not a metrics backend: one process-local snapshot, refreshed on
# every call, exposed on an ops endpoint and warned about once it gets low.

_QUOTA_WARN_FRACTION = 0.1

_quota_lock = Lock()
_quota: dict[str, object] = {}


def _parse_ratelimit_number(raw: str | None) -> int | None:
    """Groq sends plain integers for the counts. Anything else reads as absent."""
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def record_quota(headers, model: str = "") -> None:
    """Store the rate-limit headers from one response, and warn when low.

    Never raises: quota bookkeeping must not be able to fail a request that the
    provider already answered successfully.
    """
    try:
        snapshot = {
            "model": model,
            "observed_at": time.time(),
            "limit_requests": _parse_ratelimit_number(headers.get("x-ratelimit-limit-requests")),
            "remaining_requests": _parse_ratelimit_number(headers.get("x-ratelimit-remaining-requests")),
            "limit_tokens": _parse_ratelimit_number(headers.get("x-ratelimit-limit-tokens")),
            "remaining_tokens": _parse_ratelimit_number(headers.get("x-ratelimit-remaining-tokens")),
            "reset_requests": headers.get("x-ratelimit-reset-requests"),
            "reset_tokens": headers.get("x-ratelimit-reset-tokens"),
        }
    except Exception:  # noqa: BLE001 — a header shape we did not expect
        return

    with _quota_lock:
        _quota.update(snapshot)

    limit = snapshot["limit_requests"]
    remaining = snapshot["remaining_requests"]
    if limit and remaining is not None and remaining <= limit * _QUOTA_WARN_FRACTION:
        # Requests, not tokens: the token allowance refills every minute and
        # dipping into it is normal, while the request allowance on a free tier
        # is a daily budget that does not come back until it resets.
        logger.warning(
            "groq quota low: %s of %s requests left for %s (resets in %s)",
            remaining,
            limit,
            model or "the account",
            snapshot["reset_requests"] or "?",
        )


def quota_snapshot() -> dict:
    """The last observed provider allowance, for the ops endpoint."""
    with _quota_lock:
        return dict(_quota)


async def acomplete(client: Groq, **kwargs):
    """Non-blocking ``client.chat.completions.create(...)``. See run_blocking.

    Routed through ``with_raw_response`` when the client exposes it, so the
    provider's rate-limit headers can be recorded on the way past. ``.parse()``
    returns exactly what the plain call would — a ``ChatCompletion``, or a
    ``Stream`` when ``stream=True`` — so no caller can tell the difference.

    Falls back to the plain call when the client has no raw-response surface.
    Quota capture is telemetry: it must never decide whether a request can be
    made. Requiring it would also make ``acomplete`` reject any stand-in client
    that implements the one method it actually calls, which is a lot of coupling
    to buy a header.
    """
    completions = client.chat.completions
    raw_api = getattr(completions, "with_raw_response", None)
    if raw_api is None:
        return await run_blocking(completions.create, **kwargs)

    raw = await run_blocking(raw_api.create, **kwargs)
    record_quota(getattr(raw, "headers", {}) or {}, kwargs.get("model", ""))
    return raw.parse()



# ── Reading a completion's payload ───────────────────────────────────
#
# Every JSON-producing path below used to do the same two lines inline:
#   text = response.choices[0].message.content.strip()
#   if text.startswith("```"): <strip the fence>
# That was correct for the Llama models the app was written against, and it
# stopped being correct the moment a *reasoning* model was configured. Groq's
# gpt-oss models return their reasoning in a separate `reasoning` field and keep
# `content` clean, but Qwen writes a <think>…</think> block into `content`
# itself — so the "JSON" handed to json.loads starts with prose and every parse
# fails. The failure surfaces to the user as "the AI response was not valid
# JSON", which points at the document they uploaded rather than at the model.
#
# Centralised here so swapping a model can never reintroduce it one call site
# at a time.

_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.DOTALL | re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r"<think\b[^>]*>.*\Z", re.DOTALL | re.IGNORECASE)
_FENCE_OPEN_RE = re.compile(r"\A```[A-Za-z0-9_-]*[ \t]*\r?\n?")


def clean_model_text(raw: str | None, *, strip_fence: bool = True) -> str:
    """Strip reasoning blocks — and, for JSON callers, markdown fences.

    Order matters: the fence lives *inside* what is left after the think block
    is removed, never the other way round.

    ``strip_fence=False`` for the paths whose payload is *prose* — the chat
    reply and the AI-written recommendation blurb. A fenced code block there is
    content the user asked for, and unwrapping it would corrupt the answer;
    only the reasoning block is unwanted.
    """
    text = (raw or "").strip()
    text = _THINK_BLOCK_RE.sub("", text).strip()
    # An unterminated block means generation hit the token cap while still
    # reasoning, so there is no answer after it. Dropping it leaves an empty
    # string, and "the model returned nothing" is a far better diagnosis for the
    # caller than a JSONDecodeError on a paragraph of internal monologue.
    text = _UNCLOSED_THINK_RE.sub("", text).strip()
    if strip_fence and text.startswith("```"):
        text = _FENCE_OPEN_RE.sub("", text)
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def finish_reason(response) -> str:
    """Why the model stopped: "stop", "length", "content_filter", or "" if unknown.

    Worth checking before parsing: a completion cut off at the token ceiling is
    truncated JSON, and reporting that as "the AI response was not valid JSON"
    sends the user off to fix a document that was never the problem.
    """
    try:
        return response.choices[0].finish_reason or ""
    except (AttributeError, IndexError, TypeError):
        return ""


def completion_text(response, *, strip_fence: bool = True) -> str:
    """The usable text of a chat completion: ``clean_model_text`` of its content."""
    try:
        raw = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        return ""
    return clean_model_text(raw, strip_fence=strip_fence)


# Below this a completion is too short to be worth attempting: a semester plan
# needs room for several terms of structured JSON, and a stub that gets cut off
# mid-object is worse than a clear failure.
MIN_USEFUL_COMPLETION_TOKENS = 1500


def budget_max_tokens(prompt: str, desired: int) -> int:
    """Trim a completion budget so prompt + completion fits the account ceiling.

    Returns ``desired`` untouched when ``GROQ_MAX_REQUEST_TOKENS`` is 0, which is
    the default and what any paid tier should use.

    The prompt is measured at a deliberately pessimistic 3 characters per token
    (English prose averages closer to 4). Overestimating costs a little
    completion headroom; underestimating puts the request back over the limit and
    it is refused outright, which is the failure this exists to prevent.
    """
    ceiling = settings.GROQ_MAX_REQUEST_TOKENS
    if ceiling <= 0:
        return desired
    estimated_prompt = len(prompt) // 3 + 200
    room = ceiling - estimated_prompt
    if room >= desired:
        return desired
    # Never return something unusably small: if there is no real room, let the
    # request go out at the floor and let the provider's own error — which
    # main.py turns into an honest 429 — say so.
    return max(MIN_USEFUL_COMPLETION_TOKENS, room)


def json_kwargs() -> dict:
    """Extra kwargs for a call whose output must be structured JSON.

    See ``GROQ_JSON_REASONING_EFFORT`` for why this exists. Not applied to the
    chat/tool-calling loop, whose replies are short and whose reasoning is what
    makes the tool choices good.
    """
    effort = (settings.GROQ_JSON_REASONING_EFFORT or "").strip()
    return {"reasoning_effort": effort} if effort else {}


def vision_kwargs() -> dict:
    """Extra ``chat.completions.create`` kwargs for a call to the vision model.

    Kept out of the call sites so the three of them (degree checklist, syllabus,
    resume) cannot drift apart, and so swapping the vision model is one config
    change rather than a hunt through the services.
    """
    effort = (settings.GROQ_VISION_REASONING_EFFORT or "").strip()
    return {"reasoning_effort": effort} if effort else {}

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

