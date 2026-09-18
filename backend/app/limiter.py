import jwt
from jwt import PyJWTError
from slowapi import Limiter

from app.config import settings


def _get_client_ip(request) -> str:
    """Rate-limit key.

    By default we use the real socket peer (request.client.host). This is only
    trustworthy if uvicorn is NOT applying proxy headers for untrusted peers —
    the app is run with --no-proxy-headers so an attacker cannot spoof their IP
    via X-Forwarded-For and evade rate limits.

    Set BEHIND_PROXY=True ONLY when a reverse proxy you control sits in front and
    is configured to OVERWRITE X-Forwarded-For with the real client IP (and the
    app's own port is not reachable directly). We then read the LAST hop that the
    trusted proxy appended, which a client cannot forge past that proxy.
    """
    if settings.BEHIND_PROXY:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Rightmost entry is the one closest to our trusted proxy; leftmost is
            # client-supplied and therefore spoofable.
            return forwarded_for.split(",")[-1].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
    client = request.client
    return client.host if client else "unknown"


# One Limiter for the whole app, with authenticated routes overriding the key
# function per decorator (`key_func=user_or_ip_key`). A second Limiter instance
# would need its own `enabled` flag and its own storage, so every test fixture
# and every future kill-switch would have to remember to touch both — and the
# one that got forgotten would be silently unlimited.
limiter = Limiter(
    key_func=_get_client_ip,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI or "memory://",
)


def user_or_ip_key(request) -> str:
    """Rate-limit key for authenticated routes: the account, not the socket.

    Keying an authenticated route on the client IP fails in both directions.
    It under-limits, because one account can spread its requests over a pool of
    IPs and get an unbounded multiple of the intended budget — the export
    endpoint reads every row this account owns, so that is a cost amplifier, not
    a nuisance. And it over-limits, because a campus behind one NAT shares a
    single per-hour budget between every student on it.

    slowapi only hands the key function a `Request`, which is resolved before
    any route dependency runs, so `get_current_user` is not available here. We
    read the same access-token cookie and verify it the same way
    `deps.get_current_user` does — full signature, `exp`/`sub` required, and the
    `type` claim checked — so this is not a second, weaker way to be trusted: an
    unverifiable token simply falls back to the IP key and the route's own
    dependency still rejects it with a 401.

    The database is deliberately not consulted; a token for a deleted account
    still yields a stable key, and the route rejects the request anyway.
    """
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"require": ["exp", "sub"]},
            )
            if payload.get("type") == "access" and payload.get("sub"):
                # Prefixed so a user key can never collide with an IP key.
                return f"user:{payload['sub']}"
        except PyJWTError:
            pass
    return f"ip:{_get_client_ip(request)}"


# Applied to the row-creating CRUD routes. Chosen to be far above real use and
# far below "fill a table": onboarding is genuinely bursty — a student entering
# a full degree audit by hand, or a client replaying an import, can create a
# few hundred rows in a sitting — but at this rate reaching the export's
# MAX_ROWS_PER_TABLE (25,000) on any one table takes days of sustained
# scripting rather than minutes. Per endpoint per account, so a burst of course
# creation does not spend the budget for editing projects.
CRUD_WRITE_LIMIT = "300/hour"

# The .ics feed is unauthenticated (the token in the path is the credential),
# so it is keyed on the IP after all — there is no account to key on before the
# lookup, and keying on the path token would let one client mint an unbounded
# number of distinct limiter keys and exhaust the limiter's own storage.
# Generous on purpose: calendar clients poll unattended on their own schedule
# and a locked-out subscriber gets no error message, just a silently stale
# calendar. This is a ceiling on a runaway poller, not a usage budget.
CALENDAR_FEED_LIMIT = "300/hour"
