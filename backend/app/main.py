import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from groq import RateLimitError as GroqRateLimitError
from slowapi.errors import RateLimitExceeded

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
        if settings.COOKIE_SAMESITE.lower() == "none":
            logger.warning(
                "COOKIE_SAMESITE=none disables SameSite CSRF protection; ensure a CSRF "
                "defense is in place for state-changing requests."
            )
        if not settings.SMTP_HOST:
            logger.warning(
                "SMTP is not configured — password-reset and verification emails will be "
                "logged, not delivered. Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD in production."
            )
        if not settings.RATE_LIMIT_STORAGE_URI:
            logger.warning(
                "RATE_LIMIT_STORAGE_URI is unset — rate limits are per-process and reset on "
                "restart. Set a shared store (e.g. redis://) when running multiple workers."
            )
    yield


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


# Strip whitespace so `CORS_ORIGINS="https://a.com, https://b.com"` (space after
# the comma — a very common .env mistake) doesn't silently fail to match the
# space-prefixed origin. The lifespan safety check already strips; match it here.
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


# Added last so it wraps as much as possible (CORS, security headers, rate
# limiting, routing): assigns/propagates X-Request-ID, binds it to the logging
# context, and emits the single canonical request-completion log line.
install_request_id_middleware(app)

from app.routers import auth, users, conversations, degree, projects, career, suggestions, course_advisor, dashboard, dsa, study, calendar

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
app.include_router(degree.router, prefix="/degree", tags=["degree"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(career.router, prefix="/career", tags=["career"])
app.include_router(suggestions.router, prefix="/suggestions", tags=["suggestions"])
app.include_router(course_advisor.router, prefix="/course-advisor", tags=["course-advisor"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(dsa.router, prefix="/dsa", tags=["dsa"])
app.include_router(study.router, prefix="/study", tags=["study"])
app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])


@app.get("/health")
async def health():
    return {"status": "ok"}
