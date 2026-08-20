"""Coverage-raising tests for app.services.semester_plan.

Focuses on the deterministic post-processing pipeline (the part that actually
protects users from a hallucinated plan): catalog validation, prerequisite
DEFERRAL, GPA-gate flagging, capacity capping, credit padding, and the
streaming JSON extractors. Plus two hermetic end-to-end runs (Groq mocked) of
generate_semester_plan / apply_semester_plan.

Codes are routed through ``normalize_course_code`` so the tests stay correct
regardless of the canonicalizer's exact spacing rules.
"""

import json
import types
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.catalog import CatalogCourse
from app.models.degree import Course, CourseStatus, DegreeRequirement
from app.models.user import User
from app.services.auth import hash_password
from app.services.document_parser import normalize_course_code as _n
from app.services.semester_plan import (
    MAX_COURSES_PER_SEMESTER,
    PlanGenerationError,
    _build_future_semesters,
    _extract_json_from_stream,
    _pad_plan_to_target,
    _prepare_course,
    _sanitize_plan,
    _stream_prepare_semester,
    _term_sort_key,
    _try_parse_partial_semesters,
    apply_semester_plan,
    generate_semester_plan,
)


# ── Groq mock (mirrors test_advising_validity) ───────────────────────

class _MockChoice:
    def __init__(self, content):
        self.message = types.SimpleNamespace(content=content)


class _StreamChunk:
    def __init__(self, text):
        self.choices = [types.SimpleNamespace(delta=types.SimpleNamespace(content=text))]


class _MockCompletions:
    def __init__(self, content, chunks=None):
        self._content = content
        self._chunks = chunks

    def create(self, *args, **kwargs):
        if kwargs.get("stream"):
            # Emit the payload split into chunks so the partial-parser runs.
            pieces = self._chunks if self._chunks is not None else [self._content]
            return iter(_StreamChunk(p) for p in pieces)
        return types.SimpleNamespace(choices=[_MockChoice(self._content)])


class _MockGroqClient:
    def __init__(self, content, chunks=None):
        self.chat = types.SimpleNamespace(completions=_MockCompletions(content, chunks))


def _entry(raw_code, name, credits, prereqs=None, gate=None):
    e = {
        "course_code": _n(raw_code),
        "course_name": name,
        "credits": credits,
        "prerequisites": prereqs or [],
    }
    if gate is not None:
        e["gpa_gate"] = gate
    return e


# ── _term_sort_key ───────────────────────────────────────────────────

def test_term_sort_key_orders_by_year_then_season():
    terms = ["Fall 2027", "Winter 2026", "Summer 2026", "Winter 2027", "Fall 2026"]
    assert sorted(terms, key=_term_sort_key) == [
        "Winter 2026",
        "Summer 2026",
        "Fall 2026",
        "Winter 2027",
        "Fall 2027",
    ]


def test_term_sort_key_handles_garbage():
    assert _term_sort_key("") == (0, 99)
    assert _term_sort_key("Notaseason 2030") == (2030, 99)


# ── _prepare_course ──────────────────────────────────────────────────

def _prep(course, catalog, existing=None, completed=None, placed=None, this=None):
    return _prepare_course(
        course,
        catalog=catalog,
        all_existing_codes=existing or set(),
        already_completed=completed or set(),
        placed_codes=placed or set(),
        this_codes=this if this is not None else [],
    )


def test_prepare_course_drops_empty_dup_and_completed():
    cat = {_n("CS100"): _entry("CS100", "Intro", 3.0)}
    assert _prep({"course_code": ""}, cat) is None
    assert _prep({"course_code": "CS100"}, cat, placed={_n("CS100")}) is None
    assert _prep({"course_code": "CS100"}, cat, this=[_n("CS100")]) is None
    assert _prep({"course_code": "CS100"}, cat, completed={_n("CS100")}) is None


def test_prepare_course_drops_fabricated_when_catalog_present():
    cat = {_n("CS100"): _entry("CS100", "Intro", 3.0)}
    assert _prep({"course_code": "CS999"}, cat) is None  # not in a loaded catalog


def test_prepare_course_overwrites_name_credits_from_catalog():
    cat = {_n("CS100"): _entry("CS100", "Real Name", 6.0)}
    course = {"course_code": "CS100", "course_name": "LLM guess", "credits": 1.0}
    result = _prep(course, cat, existing={_n("CS100")})
    assert result is not None
    code, entry = result
    assert code == _n("CS100")
    assert course["course_name"] == "Real Name"  # authoritative overwrite
    assert course["credits"] == 6.0
    assert course["already_in_plan"] is True


def test_prepare_course_fails_open_with_empty_catalog():
    course = {"course_code": "CS100", "course_name": "Keep me", "credits": 3.0}
    result = _prep(course, {})
    assert result is not None
    code, entry = result
    assert code == _n("CS100")
    assert entry is None
    assert course["course_name"] == "Keep me"  # untouched
    assert course["already_in_plan"] is False


# ── _sanitize_plan: deferral, gate flag, fabrication drop ────────────

def _make_ctx(catalog, gpa_by_scope=None, completed=None, all_codes=None, **extra):
    ctx = {
        "all_codes": all_codes or set(),
        "catalog": catalog,
        "gpa_by_scope": gpa_by_scope or {},
        "completed_codes": completed or set(),
    }
    ctx.update(extra)
    return ctx


@pytest.fixture
def frozen_today(monkeypatch):
    class MockDate:
        @classmethod
        def today(cls):
            return date(2026, 2, 15)  # Winter 2026

    monkeypatch.setattr("app.services.semester_plan.date", MockDate)


def test_sanitize_defers_course_past_its_prerequisite(frozen_today):
    catalog = {
        _n("CS100"): _entry("CS100", "Intro", 3.0),
        _n("CS200"): _entry("CS200", "Data Structures", 3.0, prereqs=[["CS100"]]),
    }
    ctx = _make_ctx(catalog)
    plan = {"semesters": [
        {"term": "Fall 2026", "courses": [
            {"course_code": "CS200"},  # prereq co-scheduled → must defer
            {"course_code": "CS100"},
        ]},
        {"term": "Winter 2027", "courses": []},
    ]}
    out = _sanitize_plan(plan, ctx)
    fall = next(s for s in out["semesters"] if s["term"] == "Fall 2026")
    winter = next(s for s in out["semesters"] if s["term"] == "Winter 2027")
    assert [c["course_code"] for c in fall["courses"]] == [_n("CS100")]
    assert [c["course_code"] for c in winter["courses"]] == [_n("CS200")]
    assert "blocked_reason" not in winter["courses"][0]  # prereq now met


def test_sanitize_flags_gpa_gate_but_does_not_defer(frozen_today):
    catalog = {
        _n("CS300"): _entry("CS300", "Gated", 3.0, gate={"scope": "CS", "min": 4.5}),
    }
    ctx = _make_ctx(catalog, gpa_by_scope={"CS": 3.0})
    plan = {"semesters": [
        {"term": "Fall 2026", "courses": [{"course_code": "CS300"}]},
        {"term": "Winter 2027", "courses": []},
    ]}
    out = _sanitize_plan(plan, ctx)
    fall = next(s for s in out["semesters"] if s["term"] == "Fall 2026")
    assert fall["courses"][0]["course_code"] == _n("CS300")
    assert "blocked_reason" in fall["courses"][0]
    assert "4.50" in fall["courses"][0]["blocked_reason"]


def test_sanitize_drops_fabricated_and_past_semesters(frozen_today):
    catalog = {_n("CS100"): _entry("CS100", "Intro", 3.0)}
    ctx = _make_ctx(catalog)
    plan = {"semesters": [
        {"term": "Fall 2025", "courses": [{"course_code": "CS100"}]},  # past → dropped
        {"term": "Fall 2026", "courses": [
            {"course_code": "CS100"},
            {"course_code": "FAKE999"},  # not in catalog → dropped
        ]},
    ]}
    out = _sanitize_plan(plan, ctx)
    assert len(out["semesters"]) == 1
    assert out["semesters"][0]["term"] == "Fall 2026"
    assert [c["course_code"] for c in out["semesters"][0]["courses"]] == [_n("CS100")]


def test_sanitize_overflow_last_semester_produces_warning(frozen_today):
    codes = [f"CS1{i}0" for i in range(7)]  # 7 independent courses
    catalog = {_n(c): _entry(c, f"C{i}", 3.0) for i, c in enumerate(codes)}
    ctx = _make_ctx(catalog)
    plan = {"semesters": [
        {"term": "Fall 2026", "courses": [{"course_code": c} for c in codes]},
    ]}
    out = _sanitize_plan(plan, ctx)
    assert len(out["semesters"][0]["courses"]) == MAX_COURSES_PER_SEMESTER
    assert "Capped to" in out["semesters"][0]["semester_notes"]
    assert any("Not enough room" in w for w in out["warnings"])


# ── _pad_plan_to_target ──────────────────────────────────────────────

def test_pad_fills_electives_toward_credit_total():
    ctx = {
        "summary": {"total_credits_required": 120.0, "total_credits_completed": 90.0},
        "planned": [],
        "in_progress": [],
    }
    plan = {"semesters": [
        {"term": "Fall 2026", "courses": [{"course_code": "CS100", "credits": 3.0}]},
        {"term": "Winter 2027", "courses": []},
    ]}
    out = _pad_plan_to_target(plan, ctx)
    placeholders = [c for s in out["semesters"] for c in s["courses"] if c.get("is_placeholder")]
    # 90 + 3 = 93, gap 27 → 9 electives; 2 sems × 5 slots − 1 taken = 9 slots.
    assert len(placeholders) == 9
    assert not any("more elective credits" in w for w in out.get("warnings", []))


def test_pad_warns_when_target_unreachable():
    ctx = {
        "summary": {"total_credits_required": 120.0, "total_credits_completed": 0.0},
        "planned": [],
        "in_progress": [],
    }
    plan = {"semesters": [{"term": "Fall 2026", "courses": []}]}
    out = _pad_plan_to_target(plan, ctx)
    assert any("more elective credits" in w for w in out["warnings"])


def test_pad_no_op_when_gap_small_and_counts_existing_credits():
    ctx = {
        "summary": {"total_credits_required": 120.0, "total_credits_completed": 100.0},
        "planned": [types.SimpleNamespace(credit_value=9.0, course_code="X100")],
        "in_progress": [types.SimpleNamespace(credit_value=9.0, course_code="X200")],
    }
    plan = {"semesters": [{"term": "Fall 2026", "courses": [{"course_code": "CS100", "credits": 3.0}]}]}
    out = _pad_plan_to_target(plan, ctx)
    # 100 + 3 + 18 = 121 ≥ 120 → gap < 3 → nothing added.
    assert not any(c.get("is_placeholder") for s in out["semesters"] for c in s["courses"])


# ── streaming JSON extractors ────────────────────────────────────────

def test_extract_json_from_stream_variants():
    assert _extract_json_from_stream("no json here") is None
    assert json.loads(_extract_json_from_stream('{"a": 1}')) == {"a": 1}
    fenced = '```json\n{"a": {"b": 2}, "s": "has } brace"}\n```'
    assert json.loads(_extract_json_from_stream(fenced)) == {"a": {"b": 2}, "s": "has } brace"}
    assert json.loads(_extract_json_from_stream('{"x": 1} trailing')) == {"x": 1}


def test_try_parse_partial_semesters_extracts_summary_and_complete_objects():
    partial = (
        '{"plan_summary": "Two terms planned.", "semesters": ['
        '{"term": "Fall 2026", "courses": []},'
        '{"term": "Winter 2027", "courses": [{"course_code": "CS200"'  # incomplete
    )
    info, sems = _try_parse_partial_semesters(partial)
    assert info["plan_summary"] == "Two terms planned."
    assert [s["term"] for s in sems] == ["Fall 2026"]  # only the complete object


def test_try_parse_partial_semesters_no_semesters_key():
    info, sems = _try_parse_partial_semesters('{"plan_summary": "hi"}')
    assert info == {"plan_summary": "hi"}
    assert sems == []


def test_stream_prepare_semester_caps_dedups_and_flags():
    catalog = {
        _n("CS100"): _entry("CS100", "Intro", 3.0),
        _n("CS300"): _entry("CS300", "Gated", 3.0, gate={"scope": "CS", "min": 4.5}),
    }
    ctx = {"catalog": catalog, "gpa_by_scope": {"CS": 3.0}, "all_codes": set(), "completed_codes": set()}
    scheduled, placed = set(), {_n("CS100")}  # CS100 already placed earlier
    sem = {"term": "Fall 2026", "courses": [
        {"course_code": "CS100"},  # dup of already-placed → dropped
        {"course_code": "CS300"},  # gated → flagged, kept
        {"course_code": "FAKE"},   # fabricated → dropped
    ]}
    has = _stream_prepare_semester(sem, ctx, scheduled, placed)
    assert has is True
    assert [c["course_code"] for c in sem["courses"]] == [_n("CS300")]
    assert "blocked_reason" in sem["courses"][0]


# ── _build_future_semesters edge case ────────────────────────────────

def test_build_future_semesters_skip_winters_and_default_horizon(frozen_today):
    res = _build_future_semesters(None, skip_winters=True)  # grad_year None → +3 yrs
    assert all("Winter" not in s for s in res)
    assert "Fall 2029" in res  # horizon = current_year + 3


# ── end-to-end (Groq mocked) ─────────────────────────────────────────

@pytest.fixture
async def planner_user(db):
    user = User(
        id=uuid.uuid4(),
        email="planner@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Planner",
        university="Test University",
        program="Computer Science",
        start_year=2025,
        expected_graduation_year=2028,
    )
    db.add(user)
    await db.flush()
    db.add(DegreeRequirement(user_id=user.id, bucket_name="CS Core", credits_required=42.0))
    for code, name, credits, prereqs in [
        ("CS100", "Intro to CS", 3.0, []),
        ("CS200", "Data Structures", 3.0, [["CS100"]]),
    ]:
        db.add(CatalogCourse(
            id=uuid.uuid4(), university="Test University",
            course_code=code, course_name=name, credits=credits, prerequisites=prereqs,
        ))
    db.add(Course(
        user_id=user.id, course_code="CS100", course_name="Intro to CS",
        credit_value=3.0, status=CourseStatus.completed, term="Fall 2025", grade="A",
    ))
    await db.commit()
    return user


async def test_generate_semester_plan_end_to_end(planner_user, db, monkeypatch):
    payload = json.dumps({
        "plan_summary": "Finish the core.",
        "semesters": [
            {"term": "Fall 2099", "courses": [
                {"course_code": "CS200", "course_name": "wrong", "credits": 99},
                {"course_code": "GHOST101", "course_name": "Fake", "credits": 3.0},
            ], "semester_notes": ""},
        ],
        "warnings": [],
    })
    monkeypatch.setattr(
        "app.services.semester_plan.get_groq_client", lambda: _MockGroqClient(payload)
    )
    plan = await generate_semester_plan(planner_user.id, db)

    all_courses = [c for s in plan["semesters"] for c in s["courses"]]
    codes = {c["course_code"] for c in all_courses}
    assert _n("CS200") in codes
    assert _n("GHOST101") not in codes  # fabricated dropped
    cs200 = next(c for c in all_courses if c["course_code"] == _n("CS200"))
    assert cs200["credits"] == 3.0  # catalog credits overwrote the bogus 99
    assert any(c.get("is_placeholder") for c in all_courses)  # padded toward total


async def test_generate_semester_plan_rejects_an_unparseable_response(planner_user, db, monkeypatch):
    """Prose instead of a plan is a failure, and must be reported as one.

    This used to return HTTP 200 with plan_summary="Failed to parse plan. Raw AI
    response below." and the model's raw output stuffed into `warnings` — a list
    the UI renders to the student. A dump of half-written JSON is not a warning,
    and dressing a failure as a successful plan hides it from every caller.
    """
    monkeypatch.setattr(
        "app.services.semester_plan.get_groq_client",
        lambda: _MockGroqClient("this is not json at all"),
    )
    with pytest.raises(PlanGenerationError):
        await generate_semester_plan(planner_user.id, db)


async def test_generate_semester_plan_salvages_a_truncated_response(planner_user, db, monkeypatch):
    """A plan cut off mid-object still contains whole terms; keep them.

    Running out of completion budget is the common failure — especially on an
    account with a low per-request token cap — and the terms that did finish are
    a usable answer. Discarding them because the last one is incomplete throws
    away work the student can act on.
    """
    truncated = (
        '{"plan_summary": "Front-load the core.", "semesters": ['
        '{"term": "Fall 2099", "courses": [{"course_code": "CS200", '
        '"course_name": "Data Structures", "credits": 3.0}], "semester_notes": ""},'
        '{"term": "Winter 2100", "courses": [{"course_code": "CS2'
    )
    monkeypatch.setattr(
        "app.services.semester_plan.get_groq_client",
        lambda: _MockGroqClient(truncated),
    )
    plan = await generate_semester_plan(planner_user.id, db)

    assert plan["plan_summary"] == "Front-load the core."
    terms = [s["term"] for s in plan["semesters"]]
    assert "Fall 2099" in terms
    # The salvage warning names what happened; the raw model text never appears.
    assert any("cut" in w.lower() or "ran out of room" in w.lower() for w in plan["warnings"])
    assert not any("course_code" in w for w in plan["warnings"])


async def test_generate_semester_plan_stream_emits_sse_events(planner_user, db, monkeypatch):
    from app.services.semester_plan import generate_semester_plan_stream

    payload = json.dumps({
        "plan_summary": "Streamed plan.",
        "semesters": [
            {"term": "Fall 2099", "courses": [
                {"course_code": "CS200", "course_name": "wrong", "credits": 99},
                {"course_code": "GHOST101", "course_name": "Fake", "credits": 3.0},
            ], "semester_notes": ""},
        ],
        "warnings": ["heads up"],
    })
    # Split so the summary is parseable before the semesters complete.
    split = payload.index('"semesters"')
    chunks = [payload[:split], payload[split:]]
    monkeypatch.setattr(
        "app.services.semester_plan.get_groq_client",
        lambda: _MockGroqClient(payload, chunks=chunks),
    )

    events = []
    async for raw in generate_semester_plan_stream(planner_user.id, db):
        assert raw.startswith("data: ") and raw.endswith("\n\n")
        events.append(json.loads(raw[len("data: "):].strip()))

    types_seen = [e["type"] for e in events]
    assert "summary" in types_seen
    assert "semester" in types_seen
    assert types_seen[-1] == "done"

    sem_events = [e for e in events if e["type"] == "semester"]
    codes = {c["course_code"] for e in sem_events for c in e["semester"]["courses"]}
    assert _n("CS200") in codes  # eligible real course kept
    assert _n("GHOST101") not in codes  # fabricated dropped mid-stream


async def test_generate_semester_plan_stream_reports_error(planner_user, db, monkeypatch):
    from app.services.semester_plan import generate_semester_plan_stream

    def _explode():
        raise RuntimeError("groq down")

    monkeypatch.setattr("app.services.semester_plan.get_groq_client", _explode)

    events = [json.loads(raw[len("data: "):].strip())
              async for raw in generate_semester_plan_stream(planner_user.id, db)]
    # The generator swallows the exception and emits a single error event.
    assert events == [{"type": "error", "message": "Plan generation failed. Please try again."}]


async def test_apply_semester_plan_adds_new_skips_existing_and_past(planner_user, db):
    result = await apply_semester_plan(
        planner_user.id,
        semesters=[
            {"term": "Fall 2020", "courses": [{"course_code": "CS050", "course_name": "Old", "credits": 3.0}]},
            {"term": "Fall 2099", "courses": [
                {"course_code": "CS100", "course_name": "Intro", "credits": 3.0},  # exists → skip
                {"course_code": "CS200", "course_name": "Data Structures", "credits": 3.0,
                 "requirement_bucket": "CS Core"},  # new → added, bucket mapped
                {"course_code": "", "course_name": "blank", "credits": 3.0},  # no code → skip
            ]},
        ],
        db=db,
    )
    assert result["added"] == 1
    assert result["skipped"] >= 3

    rows = (await db.execute(
        select(Course).where(Course.user_id == planner_user.id)
    )).scalars().all()
    added = next(c for c in rows if c.course_code == "CS200")
    assert added.status == CourseStatus.planned
    assert added.term == "Fall 2099"
    assert added.requirement_bucket_id is not None  # bucket name resolved to id
