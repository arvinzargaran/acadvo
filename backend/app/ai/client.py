import functools
import re
import time
from threading import Lock

import anyio.to_thread
from groq import APIConnectionError, APIStatusError, Groq
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


# Keep old name as alias for any remaining references
get_gemini_client = get_groq_client
