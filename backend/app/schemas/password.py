"""Shared password-strength rules.

Deliberately closer to NIST SP 800-63B than to the classic "one uppercase, one
digit, one symbol" checklist: length is what actually resists guessing, and
composition rules mostly push people toward `Password1!`. So the rules here are

  * a real length floor (12), not 8;
  * an upper bound, because bcrypt silently truncates past 72 *bytes* and a
    100 MB password body is a free DoS;
  * a blocklist of the passwords that actually show up in credential-stuffing
    lists, plus anything that is just the app's own name.

No mandatory character classes, no forced rotation.
"""

from pydantic import AfterValidator, Field
from typing import Annotated

MIN_PASSWORD_LENGTH = 12
# bcrypt hashes at most 72 bytes and ignores the rest, so anything longer gives
# a false sense of strength. Reject it rather than silently truncating.
MAX_PASSWORD_BYTES = 72

# The head of every breach-corpus list, plus this app's own vocabulary — which
# is what people actually pick when a site asks them for a password.
_COMMON_PASSWORDS = frozenset(
    {
        "123456", "123456789", "12345678", "1234567890", "password", "password1",
        "password123", "qwerty", "qwerty123", "abc123", "111111", "123123",
        "letmein", "welcome", "welcome1", "monkey", "dragon", "sunshine",
        "iloveyou", "princess", "admin", "administrator", "login", "passw0rd",
        "football", "baseball", "trustno1", "changeme", "secret", "starwars",
        "whatever", "zaq12wsx", "qazwsx", "asdfghjkl", "1q2w3e4r", "1qaz2wsx",
        "acadvo", "acadvo123", "acadvopassword",
    }
)


def _validate_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters. "
            "A short phrase you can remember is stronger than a short scramble."
        )
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes long."
        )

    collapsed = value.strip().lower()
    if collapsed in _COMMON_PASSWORDS:
        raise ValueError(
            "That password appears in public breach lists. Please choose another."
        )
    # "aaaaaaaaaaaaaa" clears the length floor but has almost no entropy.
    if len(set(value)) < 5:
        raise ValueError("Password is too repetitive. Please choose another.")

    return value


# Use in place of `str` on any field that accepts a new password.
Password = Annotated[
    str,
    Field(min_length=MIN_PASSWORD_LENGTH),
    AfterValidator(_validate_password),
]
