"""The production startup guards.

`main.py`'s lifespan refuses to boot a deployment configured in a way that would
leak sessions, open CORS, or silently render the product unusable. Those checks
are the last thing standing between a typo in `.env` and a live site, and until
now not one of them had a test — so a refactor could have removed any of them and
every suite would still have passed.

Each test below drives the real lifespan against a settings object mutated to the
bad value, and asserts it refuses.
"""
import pytest

from app.config import settings
from app.main import lifespan


async def _boot():
    """Run the app's lifespan startup, or raise whatever it raises."""
    async with lifespan(None):
        pass


@pytest.fixture
def prod(monkeypatch):
    """A production-shaped configuration that boots cleanly."""
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "COOKIE_SAMESITE", "lax")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://acadvo.app")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "ALLOW_NO_SMTP", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URI", "redis://redis:6379")
    return settings


async def test_a_correct_production_config_boots(prod):
    await _boot()


async def test_short_jwt_secret_is_refused(prod, monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "too-short")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        await _boot()


async def test_placeholder_jwt_secret_is_refused(prod, monkeypatch):
    """A 40-character placeholder is still a placeholder."""
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "change-me-" + "x" * 40)
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        await _boot()


async def test_insecure_cookies_are_refused(prod, monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        await _boot()


async def test_wildcard_cors_is_refused(prod, monkeypatch):
    """`*` with credentialed cookies is the classic account-takeover setup."""
    monkeypatch.setattr(settings, "CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        await _boot()


async def test_localhost_cors_is_refused_in_production(prod, monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://acadvo.app,http://localhost:5173")
    with pytest.raises(RuntimeError, match="localhost"):
        await _boot()


async def test_samesite_none_is_refused(prod, monkeypatch):
    """SameSite=none removes the browser's own CSRF protection from auth cookies."""
    monkeypatch.setattr(settings, "COOKIE_SAMESITE", "none")
    with pytest.raises(RuntimeError, match="COOKIE_SAMESITE"):
        await _boot()


async def test_missing_smtp_is_refused(prod, monkeypatch):
    """Not a warning: no SMTP means no verification link, and every AI endpoint
    is gated on a verified address — so the stack comes up green and no user can
    reach the product."""
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    with pytest.raises(RuntimeError, match="SMTP"):
        await _boot()


async def test_no_smtp_can_be_chosen_deliberately(prod, monkeypatch):
    """A degree-tracker-only deployment is legitimate; it just has to be meant."""
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ALLOW_NO_SMTP", True)
    await _boot()


async def test_debug_mode_skips_the_production_guards(prod, monkeypatch):
    """Local dev runs on http with localhost origins and no mail server."""
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    await _boot()
