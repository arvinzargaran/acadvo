"""A string field that must be a plain http(s) URL.

These values are stored as-is and rendered into an `href` by the frontend.
React happily renders a `javascript:` href, so an unvalidated URL column is a
stored-XSS sink waiting for any feature that shows one user's data to someone
else (a shared portfolio, an export, an admin view).

Kept as `str` rather than pydantic's `HttpUrl` on purpose: `HttpUrl`
normalises what it accepts (appending a trailing slash, re-encoding), which
would silently rewrite links users pasted. This validates the scheme and
length, then stores exactly what was given.
"""

from typing import Annotated
from urllib.parse import urlparse

from pydantic import AfterValidator, Field

MAX_URL_LENGTH = 2048


def _validate_web_url(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None

    parsed = urlparse(trimmed)
    # Allowlist the two safe schemes rather than blocking known-bad ones:
    # javascript:, data:, vbscript: and file: are all script-capable or
    # information-disclosing in at least one browser.
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("URL must include a host, e.g. https://github.com/you/repo")
    return trimmed


WebUrl = Annotated[
    str | None,
    Field(default=None, max_length=MAX_URL_LENGTH),
    AfterValidator(_validate_web_url),
]
