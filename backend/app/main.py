import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from groq import APIConnectionError as GroqConnectionError
from groq import APIStatusError as GroqAPIStatusError
from groq import RateLimitError as GroqRateLimitError
from slowapi.errors import RateLimitExceeded

from app.ai.client import (
    AIDisabledError,
    AIUnavailableError,
    is_ai_enabled,
    quota_snapshot,
)
from app.database import get_db
from app.services.catalog import UniversityNotSetError
from app.config import settings
from app.limiter import limiter
from app.observability import (
    configure_logging,
    init_sentry,
    install_request_id_middleware,
)

# Structured JSON logging for the "acadvo.*" namespace + request-id propagation.
configure_logging()
# Error tracking; no-op unless SENTRY_DSN is set.
init_sentry()

logger = logging.getLogger(__name__)

# Header the SPA must send on state-changing requests. Not a token — see the
# csrf_protection middleware below for why presence alone is sufficient.
CSRF_HEADER = "X-Requested-With"

# Readiness must answer faster than whatever is polling it gives up on. Docker's
# HEALTHCHECK allows 5s and Caddy's startup gate waits on that, so a readiness
# probe that blocks on a hung connection until the driver's own timeout would be
# scored as a *failure* anyway — just several seconds later, and after tying up a
# pool connection that healthy traffic needed.
READINESS_TIMEOUT_SECONDS = 3.0

# Ensure our own ("app.*") loggers emit — uvicorn only configures its own loggers,
# so without this, INFO logs (e.g. dev email links) would be swallowed.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    _app_logger.addHandler(_handler)
_app_logger.setLevel(logging.INFO if settings.DEBUG else logging.WARNING)
_app_logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    secret = settings.JWT_SECRET_KEY or ""
    if len(secret) < 32 or secret.startswith("change-me"):
        raise RuntimeError(
            "JWT_SECRET_KEY must be set in .env to a random string of at least 32 characters "
            "(run: openssl rand -hex 32)"
        )

    # Production safety: DEBUG off is our proxy for "this is a real deployment".
    # Refuse to start with settings that would leak sessions or open CORS.
    if not settings.DEBUG:
        origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
        if not settings.COOKIE_SECURE:
            raise RuntimeError(
                "COOKIE_SECURE must be True in production so auth cookies are only "
                "sent over HTTPS (set COOKIE_SECURE=True, or DEBUG=True for local dev)."
            )
        if "*" in origins:
            raise RuntimeError("CORS_ORIGINS must not be '*' with credentialed cookies in production.")
        if any("localhost" in o or "127.0.0.1" in o for o in origins):
            raise RuntimeError(
                "CORS_ORIGINS still contains localhost in production — set it to your real domain(s)."
            )
        if any(o.startswith("http://") for o in origins):
            logger.warning("CORS_ORIGINS contains a plain-http origin in production: %s", origins)
        if settings.COOKIE_SAMESITE == "none":
            raise RuntimeError(
                "COOKIE_SAMESITE=none removes the browser's SameSite CSRF protection "
                "from the auth cookies. Use 'lax' (the default). If the app and API are "
                "on different hostnames, put them under one registrable domain "
                "(app.example.com + api.example.com) — that is same-site, so 'lax' "
                "cookies are still sent."
            )
        if not settings.SMTP_HOST and not settings.ALLOW_NO_SMTP:
            # Refuse to start, rather than warn.
            #
            # A warning was the wrong severity: with no SMTP, verification links
            # are only written to the server log, and every AI endpoint is gated
            # on a verified address. So the deployment comes up healthy, serves
            # pages, accepts signups — and not one real user can ever reach the
            # advisor, which is the product. Nothing surfaces that; the operator
            # sees a green stack and users see a permanent 403.
            #
            # Password reset is in the same position: an account locked out of a
            # forgotten password has no way back in.
            raise RuntimeError(
                "SMTP is not configured, so verification and password-reset emails "
                "cannot be delivered — and every AI feature is gated behind a verified "
                "address, so no user would be able to use the advisor at all.\n"
                "Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD, or set ALLOW_NO_SMTP=True to "
                "run deliberately without email (degree tracking and CRUD keep working; "
                "the AI features stay unreachable)."
            )
        if not settings.SMTP_HOST:
            logger.warning(
                "Running with ALLOW_NO_SMTP=True: verification and password-reset emails "
                "are logged, not delivered, so the AI features are unreachable for every user."
            )
        if not settings.RATE_LIMIT_STORAGE_URI:
            logger.warning(
                "RATE_LIMIT_STORAGE_URI is unset — rate limits are per-process and reset on "
                "restart. Set a shared store (e.g. redis://) when running multiple workers."
            )
        if is_ai_enabled() and settings.GROQ_MAX_REQUEST_TOKENS <= 0:
            # Warned, not refused, because 0 is correct on a paid tier and this
            # cannot tell the tiers apart without a network call at startup.
            #
            # Worth a line anyway: Groq applies its tokens-per-minute allowance
            # PER REQUEST, so on the free tier (8,000) the semester planner and
            # requirement research are refused outright with a 413 — every time,
            # not intermittently. The stack comes up green, health checks pass,
            # and the two most valuable features are dead with only a provider
            # error in the log to say so.
            logger.warning(
                "GROQ_MAX_REQUEST_TOKENS is 0 (no ceiling). Correct on a paid tier; on "
                "Groq's free tier set it to 8000, or the semester planner and requirement "
                "research will fail every call with a 413 (request larger than the "
                "account's per-minute token allowance)."
            )

    # Seed the catalogs that ship WITH the app.
    #
    # These 22 York courses are ground truth transcribed by hand from the
    # official 2025-2026 BSc checklist, and they lived in source with no caller:
    # every fresh deployment came up with an empty ``CatalogCourse`` table, so
    # ``catalog_status.verified`` was False for York and advising quietly fell
    # back to whatever the student had uploaded. The upsert is idempotent, so
    # this refreshes on each boot rather than duplicating, and a failure here is
    # logged rather than fatal — a missing catalog degrades honestly, and is not
    # a reason to refuse to serve the rest of the app.
    try:
        from app.data.york_cs_catalog import seed_catalog
        from app.database import async_session

        async with async_session() as db:
            seeded = await seed_catalog(db)
        logger.info("Seeded %d bundled York catalog courses.", seeded)
    except Exception:
        logger.exception("Bundled catalog seed failed; continuing without it.")

    # Background worker for program requirement research. A no-op without
    # GROQ_API_KEY, in which case the app keeps exactly the behaviour it has
    # today: honest gaps rather than guessed requirements.
    from app.research.runner import start_worker, stop_worker

    start_worker()
    try:
        yield
    finally:
        await stop_worker()


app = FastAPI(
    title="Acadvo API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


@app.exception_handler(GroqRateLimitError)
async def groq_rate_limit_handler(request: Request, exc: GroqRateLimitError):
    return JSONResponse(
        status_code=429,
        content={"detail": "AI rate limit reached. Please wait a moment and try again."},
    )


# Every other way a model call can fail, handled once for every router.
#
# Only `/conversations` used to catch these, so anywhere else — course search,
# document parsing, semester planning, the weekly summary — an unconfigured key
# or a provider outage escaped as an unhandled exception. That is a bare 500
# from Starlette's outermost error middleware, which sits *above* the CORS
# middleware: the response carries no Access-Control-Allow-Origin, so the SPA
# never sees a status at all, only "Failed to fetch". A whole feature looks like
# a network fault. Returning a JSONResponse from in here keeps it inside the
# stack, so it gets CORS headers and the UI can show what actually happened.
#
# This was found the hard way: Groq retired the model the app was configured
# with, and every AI feature failed as an un-attributable network error.


@app.exception_handler(UniversityNotSetError)
async def university_not_set_handler(request: Request, exc: UniversityNotSetError):
    # App-level so every catalog-grounded endpoint inherits it, including the
    # ones with no try/except of their own (course search, the plan stream) and
    # any added later. 409: the request is well-formed, the profile is not.
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(AIDisabledError)
async def ai_disabled_handler(request: Request, exc: AIDisabledError):
    return JSONResponse(
        status_code=503,
        content={"detail": "AI features are not configured on this server."},
    )


@app.exception_handler(AIUnavailableError)
async def ai_unavailable_handler(request: Request, exc: AIUnavailableError):
    return JSONResponse(
        status_code=503,
        content={"detail": "AI features are temporarily unavailable. Please try again shortly."},
    )


@app.exception_handler(GroqConnectionError)
async def groq_connection_handler(request: Request, exc: GroqConnectionError):
    logger.error("groq connection failure: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Could not reach the AI service. Please try again shortly."},
    )


@app.exception_handler(GroqAPIStatusError)
async def groq_api_status_handler(request: Request, exc: GroqAPIStatusError):
    # Logged with the provider's own status and message because the actionable
    # ones are all operator-side (a retired model id, a revoked key, an
    # exhausted quota) and the user-facing text must not repeat them.
    # The last observed quota goes on the same line as the error on purpose.
    # When a free tier's daily allowance runs out, every AI feature starts
    # failing at once and each one logs a provider error that says nothing about
    # why. Seeing "remaining_requests: 0, resets in 41m" beside the failure is
    # the difference between an outage investigation and reading a clock.
    logger.error(
        "groq api error: status=%s body=%s quota=%s",
        getattr(exc, "status_code", "?"),
        str(exc)[:500],
        quota_snapshot() or "unknown",
    )
    # A tokens-per-minute cap does NOT always arrive as a 429. Groq answers a
    # single request whose prompt plus max_tokens exceeds the account's TPM with
    # **413** and `code: rate_limit_exceeded` — it is refusing the size, not the
    # frequency. Reported as a generic failure it reads as "try again", which is
    # advice that cannot work: the same request is the same size next time. 429
    # plus a straight explanation is the honest answer.
    if "rate_limit" in str(exc).lower() or getattr(exc, "status_code", None) in (413, 429):
        return JSONResponse(
            status_code=429,
            content={
                "detail": "This request is larger than the AI service's current capacity "
                          "allows. Try again in a minute, or ask for a smaller plan."
            },
        )
    return JSONResponse(
        status_code=503,
        content={"detail": "The AI service rejected this request. Please try again shortly."},
    )


# Strip whitespace so `CORS_ORIGINS="https://a.com, https://b.com"` (space after
# the comma — a very common .env mistake) doesn't silently fail to match the
# space-prefixed origin. The lifespan safety check already strips; match it here.
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]


# ── Middleware ───────────────────────────────────────────────────────
#
# ORDER MATTERS, and Starlette's is the reverse of the reading order: each
# add_middleware call wraps everything registered before it, so the LAST one
# registered is the OUTERMOST. The stack below therefore ends up as
#
#     request-id  ->  CORS  ->  security headers  ->  CSRF  ->  router
#
# CORS must sit OUTSIDE the CSRF check. When CSRF rejects a request it returns
# early without calling the rest of the stack, so if CORS were inside it, that
# 403 would carry no Access-Control-Allow-Origin header and the browser would
# surface an opaque "Failed to fetch" instead of the actual status — the request
# is still blocked either way, but nobody can debug it and the SPA cannot show a
# real error message.


# Methods that cannot change state, so they need no CSRF check. HEAD/OPTIONS are
# included because the browser issues them itself (preflight).
_CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    """Require a custom header on every state-changing request.

    Auth is cookie-based, so the browser attaches credentials automatically and
    SameSite=lax is the only thing standing between us and CSRF. That is decent
    but single-layer: it does not cover a hostile page on a sibling subdomain
    (a same-site origin, e.g. after a subdomain takeover), and it silently
    weakens if a future deploy relaxes the cookie policy.

    A required custom header closes that gap cheaply. An HTML form — the classic
    CSRF vector — cannot set one at all, and any script that tries is forced
    into a CORS preflight, which the origin allowlist above rejects. The header
    value is irrelevant; only its presence matters, so there is no token to
    store, rotate, or leak.
    """
    if request.method not in _CSRF_SAFE_METHODS and CSRF_HEADER not in request.headers:
        return JSONResponse(
            status_code=403,
            content={
                "detail": f"Missing {CSRF_HEADER} header. State-changing requests must be "
                          "made by the application, not by a cross-site form."
            },
        )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


# Registered after the CSRF middleware so it wraps it — see the ordering note
# above. Preflight (OPTIONS) is handled here and short-circuits before reaching
# the CSRF check, which is why OPTIONS is in _CSRF_SAFE_METHODS anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", CSRF_HEADER],
)


# Added last so it wraps as much as possible (CORS, security headers, rate
# limiting, routing): assigns/propagates X-Request-ID, binds it to the logging
# context, and emits the single canonical request-completion log line.
install_request_id_middleware(app)

from app.deps import require_verified_email
from app.routers import auth, users, conversations, degree, projects, career, suggestions, course_advisor, dashboard, dsa, study, calendar

# Email verification gates the AI surface, not all writes.
#
# The practical abuse an unverified account enables is burning Groq budget from
# a throwaway address — every AI call costs real money and the per-IP rate limit
# does not stop someone cycling addresses. So the LLM-backed routers require a
# verified email for state-changing requests, applied at the router level so a
# newly added AI endpoint inherits the gate rather than silently opting out.
#
# Plain CRUD (courses, projects, career targets, DSA, study) stays open, because
# onboarding is built from exactly those calls — gating them would leave every
# new user unable to finish signup, which is a product outage, not a security
# win. That data is the user's own, isolated per-account and rate-limited.
#
# The AI endpoints that live inside otherwise-CRUD routers carry the dependency
# on the endpoint itself: degree's document/syllabus parsing and career's resume
# review (see those routers).
_verified = [Depends(require_verified_email)]

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(degree.router, prefix="/degree", tags=["degree"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(career.router, prefix="/career", tags=["career"])
app.include_router(dsa.router, prefix="/dsa", tags=["dsa"])
app.include_router(study.router, prefix="/study", tags=["study"])

app.include_router(conversations.router, prefix="/conversations", tags=["conversations"], dependencies=_verified)
app.include_router(course_advisor.router, prefix="/course-advisor", tags=["course-advisor"], dependencies=_verified)
app.include_router(suggestions.router, prefix="/suggestions", tags=["suggestions"], dependencies=_verified)


@app.get("/health")
async def health():
    """Liveness: this process is running and can serve a request.

    Deliberately checks nothing else. Liveness answers "should this container be
    restarted", and restarting the API because Postgres is briefly unreachable
    replaces one broken dependency with two — the app comes back cold, still
    unable to reach the database, having dropped every in-flight request.
    Dependency health is `/health/ready`.
    """
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(response: Response, db: AsyncSession = Depends(get_db)):
    """Readiness: this process can actually serve *useful* requests.

    Separate from liveness because they answer different questions, and the
    startup gate needs this one. `/health` returns 200 the instant uvicorn binds
    a socket — so a container whose database credentials are wrong reports
    healthy, Caddy's `depends_on: condition: service_healthy` opens the door, and
    an uptime monitor stays green while every real request 500s. Nothing in the
    stack notices, because nothing was measuring the thing that broke.

    Fails closed: any error reaching the database is 503, never a 200 with a
    caveat, because a caveat in a JSON body is not something a load balancer or a
    HEALTHCHECK reads.
    """
    checks: dict[str, str] = {}
    ok = True
    try:
        # `SELECT 1` through the app's own session dependency, not a private
        # connection: it proves the credentials, the network path and a free
        # connection from the same pool real requests draw on, which is exactly
        # the set of things that silently breaks between deploys.
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — any failure means "not ready"
        ok = False
        checks["database"] = "unavailable"
        # The reason goes to the log, never the response: this endpoint is
        # unauthenticated, and a driver error names hosts, ports and usernames.
        logger.error("readiness: database check failed: %s", exc)

    if not ok:
        response.status_code = 503
    return {"status": "ok" if ok else "degraded", "checks": checks}
