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

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VISION_MODEL: str = "llama-3.2-11b-vision-preview"

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
