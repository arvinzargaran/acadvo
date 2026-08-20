"""Tests for the .ics calendar feed (feed-token issuance + public fetch)."""

import re
from datetime import date

from app.models.career import TimelineCategory, TimelineEvent


def _token_from_url(url: str) -> str:
    m = re.search(r"/calendar/feed/([^./]+)\.ics", url)
    assert m, f"no token found in feed url: {url}"
    return m.group(1)


async def test_calendar_feed_token_is_created_and_stable(auth_client):
    first = await auth_client.get("/users/me/calendar-feed")
    assert first.status_code == 200
    url1 = first.json()["feed_url"]
    assert "/calendar/feed/" in url1 and url1.endswith(".ics")

    second = await auth_client.get("/users/me/calendar-feed")
    assert second.json()["feed_url"] == url1


async def test_calendar_feed_requires_auth(client):
    resp = await client.get("/users/me/calendar-feed")
    assert resp.status_code == 401


async def test_calendar_feed_regenerate_rotates_token(auth_client):
    first = await auth_client.get("/users/me/calendar-feed")
    url1 = first.json()["feed_url"]

    regenerated = await auth_client.post("/users/me/calendar-feed/regenerate")
    assert regenerated.status_code == 200
    url2 = regenerated.json()["feed_url"]
    assert url2 != url1

    # Old token no longer resolves.
    old_token = _token_from_url(url1)
    stale = await auth_client.get(f"/calendar/feed/{old_token}.ics")
    assert stale.status_code == 404


async def test_calendar_feed_unknown_token_404(client):
    resp = await client.get("/calendar/feed/not-a-real-token.ics")
    assert resp.status_code == 404


async def test_public_feed_contains_events(auth_client, db, test_user):
    db.add(TimelineEvent(
        user_id=test_user.id,
        title="Co-op application deadline",
        description="Apply before this date",
        event_date=date(2026, 9, 15),
        category=TimelineCategory.deadline,
        is_hard_deadline=True,
    ))
    await db.commit()

    issued = await auth_client.get("/users/me/calendar-feed")
    token = _token_from_url(issued.json()["feed_url"])

    feed = await auth_client.get(f"/calendar/feed/{token}.ics")
    assert feed.status_code == 200
    assert feed.headers["content-type"].startswith("text/calendar")

    body = feed.text
    assert "BEGIN:VCALENDAR" in body
    assert "END:VCALENDAR" in body
    assert "SUMMARY:Co-op application deadline" in body
    assert "DTSTART;VALUE=DATE:20260915" in body


# ── Feed encoding (RFC 5545) ─────────────────────────────────────────


def test_escape_neutralises_a_carriage_return():
    """Calendar injection.

    Escaping only "\\n" left a bare CR in the output. This file joins its lines
    with CRLF, so a value containing a CRLF became "...\\r" plus an escaped "n",
    and a parser that treats a lone CR as a line break reads whatever came next
    as a fresh iCalendar property. Course names and notes are user-influenced —
    some extracted from an uploaded document by a model — and the feed is served
    to the user's calendar client from an unauthenticated token URL.
    """
    from app.services.calendar import _escape

    out = _escape("Midterm\r\nSUMMARY:Injected")
    assert "\r" not in out
    assert out == "Midterm\\nSUMMARY:Injected"


def test_escape_handles_the_other_reserved_characters():
    from app.services.calendar import _escape

    assert _escape("a;b,c\\d") == r"a\;b\,c\\d"


def test_long_lines_are_folded_to_75_octets():
    """RFC 5545 section 3.1. A long course title otherwise emits an over-long
    line that stricter calendar clients reject outright."""
    from app.services.calendar import _fold

    folded = _fold("SUMMARY:" + "x" * 200)
    parts = folded.split("\r\n")
    assert all(len(p.encode()) <= 75 for p in parts)
    assert all(p.startswith(" ") for p in parts[1:])


def test_folding_never_splits_a_multibyte_character():
    """Splitting on octet 75 mid-codepoint would corrupt an accented title."""
    from app.services.calendar import _fold

    folded = _fold("SUMMARY:" + "é" * 80)
    # Rejoining the unfolded content must round-trip exactly.
    rejoined = "".join(
        p[1:] if i else p for i, p in enumerate(folded.split("\r\n"))
    )
    assert rejoined == "SUMMARY:" + "é" * 80


def test_short_lines_are_left_alone():
    from app.services.calendar import _fold

    assert _fold("VERSION:2.0") == "VERSION:2.0"


async def test_feed_lines_all_respect_the_octet_limit(auth_client, db, test_user):
    """End to end: whatever a student's data contains, the feed stays valid."""
    import uuid
    from datetime import date, timedelta
    from app.models.career import TimelineEvent, TimelineCategory
    from app.services.calendar import build_ics_feed

    db.add(TimelineEvent(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Deadline; with, reserved \\ characters and a very long name " + "y" * 120,
        description="Line one\r\nLine two",
        event_date=date.today() + timedelta(days=2),
        category=TimelineCategory.deadline,
    ))
    await db.commit()

    feed = await build_ics_feed(test_user.id, db)
    lines = feed.split("\r\n")
    assert all(len(line.encode()) <= 75 for line in lines)
    # The injected-looking content did not become its own property.
    assert not any(line.startswith("Line two") for line in lines)
    assert feed.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in feed
