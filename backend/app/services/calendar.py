import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.services.schedule import get_all_user_events


def _new_token() -> str:
    return secrets.token_urlsafe(24)


async def get_or_create_feed_token(user: User, db: AsyncSession) -> str:
    if not user.calendar_token:
        user.calendar_token = _new_token()
        await db.commit()
    return user.calendar_token


async def regenerate_feed_token(user: User, db: AsyncSession) -> str:
    user.calendar_token = _new_token()
    await db.commit()
    return user.calendar_token


async def get_user_by_feed_token(token: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.calendar_token == token))
    return result.scalar_one_or_none()


def feed_url_for_token(token: str) -> str:
    return f"{settings.PUBLIC_API_URL.rstrip('/')}/calendar/feed/{token}.ics"


def _escape(text: str) -> str:
    """Escape a value for an RFC 5545 property.

    The carriage return handling is the security-relevant part. Escaping only
    ``\n`` left a bare ``\r`` in the output, and this file joins its lines with
    ``\r\n`` — so text containing a CRLF became ``...\r`` + an escaped ``n``, and a
    parser that treats a lone CR as a line break reads whatever followed as a
    fresh iCalendar property. Every value here is user-influenced (course names
    and notes, some of them extracted from an uploaded document by a model), and
    the feed is served to the user's own calendar client from an unauthenticated
    token URL. Normalising every line ending to ``\n`` first, and escaping that,
    closes it.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a content line to 75 octets, per RFC 5545 section 3.1.

    Continuation lines begin with a single space. Folding counts *octets*, not
    characters, so a course title with an accent or an em dash cannot push a
    line over the limit by more than it appears to — splitting mid-codepoint
    would corrupt it, so the split points are found on the encoded bytes and
    decoded back.
    """
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks, start = [], 0
    limit = 75
    while start < len(raw):
        end = min(start + limit, len(raw))
        # Do not split inside a multi-byte character.
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1
        chunks.append(raw[start:end].decode("utf-8"))
        start = end
        limit = 74  # continuation lines carry a leading space
    return "\r\n ".join(chunks)


async def build_ics_feed(user_id: uuid.UUID, db: AsyncSession) -> str:
    """Build an RFC 5545 feed of all-day events (deadlines, milestones, assessments)."""
    events = await get_all_user_events(user_id, db)
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Acadvo//Calendar Feed//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Acadvo Deadlines",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]

    for e in events:
        if not e.get("date"):
            continue
        clean_date = e["date"].replace("-", "")

        desc_parts = []
        if e.get("source"):
            desc_parts.append(e["source"])
        if e.get("weight") is not None:
            desc_parts.append(f"Weight: {e['weight']}%")
        if e.get("notes"):
            desc_parts.append(e["notes"])
        description = " — ".join(desc_parts)

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{e['id']}@acadvo.app")
        lines.append(f"DTSTAMP:{now_stamp}")
        lines.append(f"DTSTART;VALUE=DATE:{clean_date}")
        lines.append(f"SUMMARY:{_escape(e['title'])}")
        if description:
            lines.append(f"DESCRIPTION:{_escape(description)}")
        if e.get("category"):
            lines.append(f"CATEGORIES:{e['category'].upper()}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
