from pydantic import field_validator
from pydantic_settings import BaseSettings

# The only algorithms this app is built for. Tokens are signed with a shared
# secret, so allowing an asymmetric or "none" algorithm here would let a forged
# token be verified against the secret as if it were a public key — the classic
# JWT algorithm-confusion attack.
_ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://acadvo:acadvo@db:5432/acadvo"
    DATABASE_URL_SYNC: str = "postgresql://acadvo:acadvo@db:5432/acadvo"

    JWT_SECRET_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Catalog ingestion. Waterloo's Open Data API is official and documented but
    # key-gated; registration confirms an email address, so it is the operator's
    # to obtain. Unset simply means Waterloo has no seeded catalog, which the app
    # already degrades honestly for.
    WATERLOO_API_KEY: str = ""

    GROQ_API_KEY: str = ""
    # Model IDs are not stable identifiers — Groq retires hosted models, and a
    # retired one comes back as a 404 on *every* AI call, which reads in the app
    # as "all the AI features are broken" with nothing pointing at the cause.
    # The whole Llama family this app was written against (llama-3.3-70b-versatile,
    # llama-3.2-11b-vision-preview) is gone. Check
    # `GET https://api.groq.com/openai/v1/models` before assuming a value here
    # still resolves, and re-check when AI features fail wholesale.
    #
    # gpt-oss-120b: 131k context, function calling (the advisor's 15 tools), and
    # it keeps its reasoning in a separate response field so `content` is clean.
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    # The only vision-capable model Groq currently serves. Unlike the above it
    # writes <think>…</think> into the content itself, which is why every JSON
    # path reads its output through `app.ai.client.completion_text`.
    GROQ_VISION_MODEL: str = "qwen/qwen3.8-27b"
    # Sent with every vision call, and load-bearing rather than a tuning knob.
    #
    # Left to reason freely, Qwen spends the *entire* completion budget thinking
    # and never emits the JSON: a real checklist image came back with
    # finish_reason=length after 4096 tokens of monologue, which the app reports
    # as "the AI response was not valid JSON" — blaming the user's document for
    # a budget problem. With reasoning off the same image answers in ~900 tokens
    # of clean JSON. It also keeps a single upload under the model's 8k
    # tokens-per-minute limit, which the reasoning version exceeded on its own.
    #
    # Groq accepts only "none" or "default" here for Qwen, and other models
    # reject the parameter outright — set this empty to omit it entirely.
    GROQ_VISION_REASONING_EFFORT: str = "none"
    # Hard ceiling on prompt + completion for a single Groq request, or 0 for
    # "no ceiling" (the default — a paid tier does not need this).
    #
    # Groq's per-minute token limit is also a per-REQUEST limit: a single call
    # whose prompt plus max_tokens exceeds it is refused outright with a 413,
    # every time, no matter how long you wait. On the free tier (8,000 TPM) that
    # is exactly what the semester planner does — ~900 tokens of prompt against
    # an 8,192-token completion budget — so the flagship feature fails 100% of
    # the time rather than intermittently.
    #
    # Set this to the account's TPM and the planner trims its completion budget
    # to fit instead of failing. A shorter budget means a shorter plan, which is
    # a real cost; it is still strictly better than no plan at all, and paid
    # deployments leave this at 0 and are unaffected.
    GROQ_MAX_REQUEST_TOKENS: int = 0

    # Wall-clock ceiling on a single model call, and how many times the SDK may
    # retry one on its own.
    #
    # The SDK's defaults (60s, 2 retries) compound with the app's own retry loop
    # in ai/conversation.py, which already makes AI_MAX_ATTEMPTS=3 attempts with
    # backoff: 3 x 3 attempts x 60s is roughly nine minutes for ONE model call,
    # and a chat turn makes up to MAX_TOOL_ROUNDS=10 of them. Each of those calls
    # holds a thread from anyio's 40-slot pool, so a slow (not even failed) Groq
    # is enough to exhaust the pool and stall every request the worker is
    # serving, AI or not. Retrying belongs in one place — ours, which knows what
    # is transient and logs it — so the SDK's own retries are turned off here.
    GROQ_TIMEOUT_SECONDS: float = 30.0
    GROQ_SDK_MAX_RETRIES: int = 0

    # Reasoning effort for the calls whose output is STRUCTURED JSON, as opposed
    # to the chat loop (which keeps the model's default and benefits from it).
    #
    # Measured, not guessed: on a real semester-plan prompt, gpt-oss-120b with
    # default reasoning spent all 4,631 available completion tokens thinking and
    # returned **zero characters** of plan. The same prompt at "low" returned
    # ~19k characters of JSON. Reasoning tokens come out of the same budget as
    # the answer, so on any bounded budget an unbounded thinker can starve its
    # own output — and the failure looks like a broken feature, not a setting.
    #
    # Empty string omits the parameter for models that reject it.
    GROQ_JSON_REASONING_EFFORT: str = "low"

    # ── Research: reading a university's own public pages ──────────────
    #
    # The requirement rules a student is graded against ("6.00 credits in
    # AP/HUMA") exist only as prose on calendar pages that differ per school, so
    # extracting them means reading the page rather than querying anything.
    #
    # This ran on Gemini's Search grounding until the app was moved onto the Groq
    # free tier exclusively. Nothing was lost: the page is now fetched by
    # `app.ai.research_client.fetch_page` over plain HTTPS — free, unmetered, and
    # a stronger citation than a provider's word for it, because the HTTP status
    # is ours to check. The model only ever sees text we retrieved.
    #
    # Same model as everything else, deliberately. `groq/compound` looks like the
    # better choice — it advertises a 70,000 token-per-minute limit against
    # gpt-oss-120b's 8,000, which would fit a whole calendar page. It is not: the
    # compound systems are routers that delegate to the ordinary models, so a
    # compound request is refused on *their* limits. Measured, not assumed — the
    # same request 413s under compound while its own rate-limit headers still
    # report 64,000 tokens remaining. There is no extra headroom to be had, so
    # the page is trimmed to fit instead (see RESEARCH_MAX_PAGE_CHARS).
    RESEARCH_MODEL: str = "openai/gpt-oss-120b"
    # Used only when RESEARCH_USE_SEARCH_GROUNDING is on: the system that has
    # server-side web search. A compound system is required here — it is the only
    # thing on Groq that can retrieve at all — and the ceiling above is exactly
    # why searching does not fit the free tier.
    RESEARCH_SEARCH_MODEL: str = "groq/compound"
    # Hard cap on how much of one page's text is put in front of the model, used
    # when GROQ_MAX_REQUEST_TOKENS leaves more room than this. Whole calendar
    # pages run to hundreds of kilobytes of navigation; the requirements
    # themselves are a few thousand characters, and everything past that is the
    # site's chrome repeated.
    RESEARCH_MAX_PAGE_CHARS: int = 48_000

    # How long an extracted requirement rule is trusted before it is re-checked.
    # University calendars are republished annually, so a rule older than this is
    # served (stale data beats no data) but flagged and queued for refresh.
    REQUIREMENT_RULE_TTL_DAYS: int = 180

    # Master switch for the background research worker. Off in tests, which drive
    # the research functions directly rather than through the queue.
    PROGRAM_RESEARCH_ENABLED: bool = True

    # Let the model FIND requirement pages itself (Groq compound's server-side
    # web search) instead of only reading URLs it is given.
    #
    # Off by default, and no longer for a billing reason — nothing in this app is
    # billed. A search pulls several whole pages into a single request, and Groq
    # applies its per-minute token allowance per REQUEST: on the free tier that
    # is a flat 413, every time, regardless of how long you wait. Direct fetching
    # of a supplied URL costs no tokens at all and reads the same page; the only
    # thing lost is automatic discovery, which is why a program's requirements
    # URL is supplied rather than searched for.
    #
    # Turn this on only on an account with the per-request headroom for it.
    RESEARCH_USE_SEARCH_GROUNDING: bool = False

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    DEBUG: bool = False
    BEHIND_PROXY: bool = False

    # Rate limiting. Default in-memory is per-process (limits multiply across
    # workers). Set to e.g. "redis://localhost:6379" for an exact shared limit.
    RATE_LIMIT_STORAGE_URI: str = ""

    # Email / links. When SMTP_HOST is empty, emails are logged instead of sent
    # (fine for local dev). FRONTEND_URL is used to build reset/verify links.
    FRONTEND_URL: str = "http://localhost:5173"

    # Public base URL of this API, used to build the .ics calendar feed URL
    # (calendar apps fetch this directly, so it must be internet-reachable in prod).
    PUBLIC_API_URL: str = "http://localhost:8000"
    SMTP_HOST: str = ""
    # Escape hatch for a deliberate no-email deployment. Without it the app
    # refuses to start in production with SMTP unset — see the lifespan check in
    # main.py for why that is a hard failure and not a warning.
    ALLOW_NO_SMTP: bool = False
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = True
    EMAIL_FROM: str = "no-reply@acadvo.app"
    EMAIL_FROM_NAME: str = "Acadvo"

    # Token lifetimes (minutes)
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES: int = 1440

    # Error tracking (Sentry). Leave SENTRY_DSN empty to disable entirely —
    # nothing is initialised and there is zero runtime cost. When set, traces
    # are sampled at SENTRY_TRACES_SAMPLE_RATE (0.0 = errors only, no tracing).
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def _check_jwt_algorithm(cls, v: str) -> str:
        if v not in _ALLOWED_JWT_ALGORITHMS:
            raise ValueError(
                f"JWT_ALGORITHM must be one of {sorted(_ALLOWED_JWT_ALGORITHMS)}, got {v!r}"
            )
        return v

    @field_validator("COOKIE_SAMESITE")
    @classmethod
    def _check_cookie_samesite(cls, v: str) -> str:
        normalized = v.lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError(f"COOKIE_SAMESITE must be lax, strict or none, got {v!r}")
        return normalized


settings = Settings()
