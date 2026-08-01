"""Tests for syllabus parsing (app.services.degree.parse_and_save_syllabus).

The syllabus parser must:
  - use the real (Groq) AI client, not a non-existent Gemini SDK,
  - normalize parsed due dates to timezone-aware datetimes,
  - create a timeline deadline event for dated assessments.
"""

import uuid

import pytest

import app.ai.client as ai_client
from app.models.career import TimelineEvent
from app.models.degree import Assessment, Course, CourseStatus
from app.models.user import User
from app.services import degree as degree_service
from app.services.auth import hash_password


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _Resp(self._content)


class _Chat:
    def __init__(self, content):
        self.completions = _Completions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _Chat(content)


async def _make_user_and_course(db):
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("testpass123"),
        full_name="Syllabus User",
        university="University of Toronto",
        program="Computer Science",
    )
    db.add(user)
    await db.flush()
    course = Course(
        user_id=user.id,
        course_code="CSC207",
        course_name="Software Design",
        credit_value=3.0,
        status=CourseStatus.in_progress,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return user, course


async def test_parse_syllabus_saves_assessments_with_tzaware_dates(db, monkeypatch):
    user, course = await _make_user_and_course(db)

    payload = (
        '[{"title": "Final Exam", "due_date": "2026-04-15", '
        '"weight": 50.0, "category": "exam"}]'
    )
    monkeypatch.setattr(ai_client, "get_groq_client", lambda: _FakeClient(payload))

    saved = await degree_service.parse_and_save_syllabus(
        course.id, user.id, b"fake-image-bytes", "image/png", db
    )

    # Previously this whole call raised (google.genai import / Gemini API on a
    # Groq client / NameError on `timezone`), so a dated assessment could never
    # be saved. It must now parse and persist cleanly.
    assert len(saved) == 1
    a = saved[0]
    assert a.title == "Final Exam"
    assert a.weight == 50.0
    assert a.due_date is not None
    assert (a.due_date.year, a.due_date.month, a.due_date.day) == (2026, 4, 15)

    # A deadline timeline event should have been created for the dated assessment.
    from sqlalchemy import select

    events = (
        await db.execute(select(TimelineEvent).where(TimelineEvent.user_id == user.id))
    ).scalars().all()
    assert any("Final Exam" in e.title for e in events)
