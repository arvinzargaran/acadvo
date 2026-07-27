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


limiter = Limiter(
    key_func=_get_client_ip,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI or "memory://",
)
