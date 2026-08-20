"""Eval harness for the AI course-recommendation pipeline.

Built with the `generate-synthetic-data` and `eval-audit` methodology
(hamelsmu/evals-skills). Two things that skill set insists on and that shape
this file:

  * **Dimensions target anticipated failures, not arbitrary variation.** The
    axes below are the places this pipeline can actually be wrong, not a
    generic sweep.
  * **Use code for objectively checkable criteria; reserve LLM judges for
    things needing interpretation.** Everything asserted here — "does this code
    exist", "was the gate applied", "do credits match the catalog" — is
    objective, so it is checked in code. No judge, no network, fully hermetic.

`test_advising_validity.py` already pins ONE hand-written case per failure mode
against ONE student. This adds the breadth: every failure mode is replayed
against every student state, because the validators are state-dependent and a
bug that only bites the below-GPA-gate student is invisible from a single
persona.

DIMENSIONS
----------
1. Student state — what the validator must reason about
     fresh · below_gate · above_gate · equivalent_completed
2. Model misbehaviour — what the LLM might hand back
     fabricated · already_completed · prereq_unmet · gpa_gated ·
     wrong_metadata · duplicated · wrong_bucket · malformed_json
3. Request shape — generic goal · bucket-filtered
4. Requirement-rule state — what the program's cached research says
     none · supporting · excluding

INVARIANTS (the evaluators)
---------------------------
INV1 every returned code exists in the catalog
INV2 nothing already completed (or equivalent to it) is recommended
INV3 name and credits come from the catalog, never from the model
INV4 every ineligible course is flagged BLOCKED with a reason
INV5 no duplicate codes
INV6 eligible courses sort ahead of blocked ones
INV7 malformed model output degrades to empty, never raises
INV8 no "this counts toward your degree" without a citation, and no inference
     rendered as a fact
"""

import json
import types
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.data.york_cs_catalog import YORK_CS_COURSES, YORK_UNIVERSITY
from app.models.catalog import CatalogCourse
from app.models.degree import Course, CourseStatus, DegreeRequirement
from app.models.user import User
from app.services.auth import hash_password
from app.services.catalog import get_catalog
from app.services.course_recommendation import (
    NoCatalogError,
    NoCoverageError,
    generate_recommendations,
)
from app.services.document_parser import normalize_course_code
from app.services.eligibility import (
    equivalents_of,
    evaluate_entry,
    get_completed_codes,
    gpa_by_scope_for_catalog,
)

# ── Hermetic Groq stub ───────────────────────────────────────────────


class _MockChoice:
    def __init__(self, content):
        self.message = types.SimpleNamespace(content=content)


class _MockCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, *args, **kwargs):
        return types.SimpleNamespace(choices=[_MockChoice(self._content)])


class _MockGroqClient:
    def __init__(self, content):
        self.chat = types.SimpleNamespace(completions=_MockCompletions(content))


def _patch_llm(monkeypatch, content: str) -> None:
    monkeypatch.setattr(
        "app.services.course_recommendation.get_groq_client",
        lambda: _MockGroqClient(content),
    )


# ── Catalog + persona construction ───────────────────────────────────


async def _seed_york_catalog(db):
    """SQLite-safe equivalent of ``seed_catalog`` (which uses a Postgres-only
    ON CONFLICT upsert).

    Idempotent: a single test may build several students to compare them, and
    the catalog is shared, so re-seeding must be a no-op rather than a unique
    constraint violation.
    """
    existing = await db.execute(
        select(CatalogCourse.id).where(CatalogCourse.university == YORK_UNIVERSITY).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return

    for c in YORK_CS_COURSES:
        db.add(
            CatalogCourse(
                id=uuid.uuid4(),
                university=YORK_UNIVERSITY,
                course_code=c["course_code"],
                course_name=c["course_name"],
                credits=c["credits"],
                subject_faculty=c.get("subject_faculty"),
                prerequisites=c.get("prerequisites") or [],
                gpa_gate=c.get("gpa_gate"),
            )
        )
    await db.commit()


# York 9-point scale. Low set lands EECS GPA below the 4.50 gate; high set above.
_LOW_EECS = [
    ("LE/EECS 1001", "Research Directions in Computing", 1.0, "C"),
    ("LE/EECS 1012", "Introduction to Computing: A Net-centric Approach", 3.0, "C"),
    ("LE/EECS 1022", "Introduction to Object Oriented Programming", 3.0, "C+"),
    ("LE/EECS 1019", "Discrete Mathematics for Computer Science", 3.0, "D+"),
    ("SC/MATH 1300", "Differential Calculus with Applications", 3.0, "B"),
    ("SC/MATH 1310", "Integral Calculus with Applications", 3.0, "C+"),
]
_HIGH_EECS = [
    ("LE/EECS 1001", "Research Directions in Computing", 1.0, "A"),
    ("LE/EECS 1012", "Introduction to Computing: A Net-centric Approach", 3.0, "A"),
    ("LE/EECS 1022", "Introduction to Object Oriented Programming", 3.0, "A"),
    ("LE/EECS 1019", "Discrete Mathematics for Computer Science", 3.0, "A"),
    ("SC/MATH 1300", "Differential Calculus with Applications", 3.0, "A"),
    ("SC/MATH 1310", "Integral Calculus with Applications", 3.0, "A"),
]
# Same standing as _HIGH_EECS but took the OTHER intro (1015, not 1012). The
# pipeline must treat 1012 as already satisfied via EQUIVALENT_GROUPS.
_EQUIVALENT = [
    ("LE/EECS 1001", "Research Directions in Computing", 1.0, "A"),
    ("LE/EECS 1015", "Introduction to Computer Science and Programming", 3.0, "A"),
    ("LE/EECS 1022", "Introduction to Object Oriented Programming", 3.0, "A"),
    ("LE/EECS 1019", "Discrete Mathematics for Computer Science", 3.0, "A"),
]

STUDENT_STATES = {
    "fresh": [],
    "below_gate": _LOW_EECS,
    "above_gate": _HIGH_EECS,
    "equivalent_completed": _EQUIVALENT,
}


async def _make_student(db, state: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{state}-{uuid.uuid4().hex[:8]}@my.yorku.ca",
        hashed_password=hash_password("testpass123"),
        full_name=f"Eval {state}",
        university=YORK_UNIVERSITY,
        program="Computer Science",
        start_year=2024,
        expected_graduation_year=2028,
    )
    db.add(user)
    await db.flush()

    for bucket_name, credits in [
        ("Computer Science Core", 42.0),
        ("Mathematics", 12.0),
        ("General Education", 12.0),
    ]:
        db.add(
            DegreeRequirement(
                user_id=user.id, bucket_name=bucket_name, credits_required=credits
            )
        )

    for code, name, credits, grade in STUDENT_STATES[state]:
        db.add(
            Course(
                user_id=user.id,
                course_code=code,
                course_name=name,
                credit_value=credits,
                status=CourseStatus.completed,
                term="Fall 2024",
                grade=grade,
            )
        )

    await _seed_york_catalog(db)
    await db.commit()
    return user


# ── Adversarial payloads (dimension 2) ───────────────────────────────


def _rec(code, **over):
    """One recommendation object as the model would emit it."""
    base = {
        "course_code": code,
        "course_name": "Model-Supplied Name",
        "credits": 99.0,
        "requirement_bucket": "Computer Science Core",
        "reasoning": "because",
        "career_relevance": "software",
        "prerequisite_notes": "",
        "priority": "high",
    }
    base.update(over)
    return base


MISBEHAVIOURS = {
    # A code that does not exist anywhere in the catalog.
    "fabricated": json.dumps([_rec("LE/EECS 4040"), _rec("SC/MATH 9999")]),
    # Courses the student has already finished.
    "already_completed": json.dumps([_rec("LE/EECS 1022"), _rec("SC/MATH 1300")]),
    # Real course whose prerequisites the student has not met.
    "prereq_unmet": json.dumps([_rec("LE/EECS 3101")]),
    # Real course behind the 4.50 EECS GPA gate.
    "gpa_gated": json.dumps([_rec("LE/EECS 2030"), _rec("LE/EECS 2031")]),
    # Real code, but the model invented the name and credits.
    "wrong_metadata": json.dumps(
        [_rec("LE/EECS 2030", course_name="Totally Wrong Name", credits=42.0)]
    ),
    # Same code twice.
    "duplicated": json.dumps([_rec("LE/EECS 2030"), _rec("LE/EECS 2030")]),
    # An EECS course filed under a wet-lab science bucket.
    "wrong_bucket": json.dumps(
        [_rec("LE/EECS 2030", requirement_bucket="Foundational Science Lab")]
    ),
    # Output that is not parseable as the contract.
    "malformed_json": "I'm sorry, I can't help with that. Here's some prose instead.",
    # Valid JSON wrapped in the markdown fence the model is told not to emit.
    "fenced_json": "```json\n" + json.dumps([_rec("LE/EECS 2030")]) + "\n```",
}


# ── Evaluators (code-based, per eval-audit guidance) ─────────────────


async def _catalog_for(user, db):
    return await get_catalog(YORK_UNIVERSITY, db, user.id)


async def _assert_invariants(recs, user, db, state):
    """Run every invariant that must hold for ANY model output, on ANY student."""
    catalog = await _catalog_for(user, db)
    completed = await get_completed_codes(user.id, db)
    gpa_by_scope = await gpa_by_scope_for_catalog(catalog, user.id, db)

    codes = [r.course_code for r in recs]

    # INV1 — every code is real.
    for code in codes:
        assert code in catalog, f"[{state}] hallucinated code survived: {code}"

    # INV2 — nothing already completed (or equivalent) is recommended.
    for code in codes:
        assert not (equivalents_of(code) & completed), (
            f"[{state}] recommended an already-completed course: {code}"
        )

    # INV3 — metadata is the catalog's, not the model's.
    for r in recs:
        entry = catalog[r.course_code]
        assert r.course_name == entry["course_name"], (
            f"[{state}] model name survived for {r.course_code}"
        )
        assert float(r.credits) == float(entry["credits"]), (
            f"[{state}] model credits survived for {r.course_code}"
        )

    # INV4 — ineligible courses are flagged, with a reason.
    for r in recs:
        reason = evaluate_entry(catalog[r.course_code], completed, gpa_by_scope)
        if reason is not None:
            notes = r.prerequisite_notes or ""
            assert "BLOCKED" in notes, (
                f"[{state}] ineligible {r.course_code} not flagged BLOCKED"
            )

    # INV5 — no duplicates.
    assert len(codes) == len(set(codes)), f"[{state}] duplicate codes: {codes}"

    # INV6 — eligible before blocked.
    blocked_flags = [
        evaluate_entry(catalog[r.course_code], completed, gpa_by_scope) is not None
        for r in recs
    ]
    assert blocked_flags == sorted(blocked_flags), (
        f"[{state}] blocked course sorted ahead of an eligible one"
    )

    # INV8 — the degree-credit claim is never made bare.
    #
    # This is the one error in the product that fails silently: a student is told
    # a course counts, plans around it, and finds out at their graduation audit.
    # So a positive verdict must be traceable (it names the pages it came from)
    # and, when it is Acadvo's conclusion rather than the university's words, it
    # must say so in the very string a UI would render.
    for r in recs:
        verdict = r.bucket_verdict
        if not verdict or not verdict.get("counts"):
            continue
        assert verdict.get("source_urls"), (
            f"[{state}] {r.course_code} claims to satisfy "
            f"{verdict.get('bucket_name')!r} with no source"
        )
        if verdict.get("certainty") == "inferred":
            assert verdict["is_inference"] is True
            assert "Likely" in verdict["label"], (
                f"[{state}] inferred verdict for {r.course_code} reads as a fact: "
                f"{verdict['label']!r}"
            )


# ── The matrix ───────────────────────────────────────────────────────


@pytest.mark.parametrize("state", sorted(STUDENT_STATES))
@pytest.mark.parametrize("misbehaviour", sorted(MISBEHAVIOURS))
async def test_invariants_hold_across_matrix(state, misbehaviour, db, monkeypatch):
    """Every invariant holds for every (student state x model misbehaviour)."""
    user = await _make_student(db, state)
    _patch_llm(monkeypatch, MISBEHAVIOURS[misbehaviour])

    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)

    await _assert_invariants(recs, user, db, f"{state}/{misbehaviour}")


# ── Targeted assertions per failure mode ─────────────────────────────


@pytest.mark.parametrize("state", sorted(STUDENT_STATES))
async def test_fabricated_codes_are_dropped_entirely(state, db, monkeypatch):
    user = await _make_student(db, state)
    _patch_llm(monkeypatch, MISBEHAVIOURS["fabricated"])
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs == [], f"[{state}] fabricated codes produced recommendations"


@pytest.mark.parametrize("state", sorted(STUDENT_STATES))
async def test_malformed_output_degrades_to_empty(state, db, monkeypatch):
    """INV7 — prose instead of JSON must not raise; it yields nothing."""
    user = await _make_student(db, state)
    _patch_llm(monkeypatch, MISBEHAVIOURS["malformed_json"])
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs == []


@pytest.mark.parametrize("state", sorted(STUDENT_STATES))
async def test_fenced_json_is_still_parsed(state, db, monkeypatch):
    """The model is told not to fence its JSON; when it does anyway, the answer
    must still survive rather than being silently discarded."""
    user = await _make_student(db, state)
    _patch_llm(monkeypatch, MISBEHAVIOURS["fenced_json"])
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert [r.course_code for r in recs] == ["LE/EECS 2030"]


async def test_gate_blocks_below_but_not_above(db, monkeypatch):
    """The 4.50 EECS gate is the single most consequential rule in the product:
    it must bite the student below it and stay out of the way above it."""
    below = await _make_student(db, "below_gate")
    _patch_llm(monkeypatch, MISBEHAVIOURS["gpa_gated"])
    recs = await generate_recommendations(below.id, "Winter 2025", "both", None, db)
    assert recs, "gated courses should be surfaced-with-reason, not dropped"
    for r in recs:
        assert "BLOCKED" in (r.prerequisite_notes or "")
        assert "4.50" in r.prerequisite_notes

    above = await _make_student(db, "above_gate")
    _patch_llm(monkeypatch, MISBEHAVIOURS["gpa_gated"])
    recs = await generate_recommendations(above.id, "Winter 2025", "both", None, db)
    assert recs
    for r in recs:
        assert "BLOCKED" not in (r.prerequisite_notes or ""), (
            f"{r.course_code} blocked for a student who clears the gate"
        )


async def test_equivalent_intro_counts_as_completed(db, monkeypatch):
    """A student who took EECS 1015 must never be offered its equivalent 1012."""
    user = await _make_student(db, "equivalent_completed")
    _patch_llm(monkeypatch, json.dumps([_rec("LE/EECS 1012")]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert [r.course_code for r in recs] == [], (
        "offered LE/EECS 1012 to a student who completed the equivalent 1015"
    )


async def test_model_metadata_never_reaches_the_student(db, monkeypatch):
    user = await _make_student(db, "above_gate")
    _patch_llm(monkeypatch, MISBEHAVIOURS["wrong_metadata"])
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.course_name != "Totally Wrong Name"
    assert float(rec.credits) != 42.0


async def test_eecs_course_is_not_filed_as_a_lab_science(db, monkeypatch):
    """EECS/MATH courses can never satisfy the wet-lab science bucket."""
    user = await _make_student(db, "above_gate")
    _patch_llm(monkeypatch, MISBEHAVIOURS["wrong_bucket"])
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert len(recs) == 1
    assert "lab" not in (recs[0].requirement_bucket or "").lower()


async def _student_with_uploaded_checklist(db, university: str, courses: list[dict]):
    """A student who has uploaded their degree checklist: a row per requirement,
    two completed, everything else `not_scheduled` (required, not yet taken)."""
    user = User(
        id=uuid.uuid4(),
        email=f"checklist-{uuid.uuid4().hex[:8]}@x.ca",
        hashed_password=hash_password("testpass123"),
        full_name="Checklist Student",
        university=university,
        program="Computer Science",
        start_year=2023,
        expected_graduation_year=2027,
    )
    db.add(user)
    await db.flush()
    db.add(
        DegreeRequirement(
            user_id=user.id, bucket_name="CS Core", credits_required=42.0
        )
    )
    for i, c in enumerate(courses):
        db.add(
            Course(
                user_id=user.id,
                course_code=c["course_code"],
                course_name=c["course_name"],
                credit_value=c["credits"],
                status=CourseStatus.completed if i < 2 else CourseStatus.not_scheduled,
                grade="A" if i < 2 else None,
            )
        )
    await db.commit()
    return user


async def test_uploaded_checklist_does_not_silence_the_advisor(db, monkeypatch):
    """The regression that mattered most.

    A `not_scheduled` row means "this is required and I have not scheduled it" —
    the single best thing an advisor can recommend. It was being treated as
    "already in plan", so a York student who uploaded their checklist excluded
    their entire program from advice and got nothing back. The more completely
    they filled in their degree, the less the advisor could say.
    """
    await _seed_york_catalog(db)
    user = await _student_with_uploaded_checklist(db, YORK_UNIVERSITY, YORK_CS_COURSES)

    # A course sitting at `not_scheduled` in the student's checklist.
    target = YORK_CS_COURSES[5]["course_code"]
    _patch_llm(monkeypatch, json.dumps([_rec(target)]))

    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert [r.course_code for r in recs] == [normalize_course_code(target)], (
        "an unscheduled requirement was withheld from recommendations"
    )


async def test_completed_and_scheduled_courses_are_still_excluded(db, monkeypatch):
    """The other half: loosening the filter must not start re-recommending
    courses the student has finished or already timetabled."""
    await _seed_york_catalog(db)
    user = await _student_with_uploaded_checklist(db, YORK_UNIVERSITY, YORK_CS_COURSES)

    completed_code = YORK_CS_COURSES[0]["course_code"]
    _patch_llm(monkeypatch, json.dumps([_rec(completed_code)]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs == [], "re-recommended a completed course"

    # Now schedule one, and confirm it drops out too.
    scheduled_code = YORK_CS_COURSES[7]["course_code"]
    row = await db.execute(
        select(Course).where(
            Course.user_id == user.id, Course.course_code == scheduled_code
        )
    )
    course = row.scalar_one()
    course.status = CourseStatus.planned
    await db.commit()

    _patch_llm(monkeypatch, json.dumps([_rec(scheduled_code)]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs == [], "re-recommended an already-scheduled course"


async def test_uncatalogued_university_still_fails_loudly(db, monkeypatch):
    """A student at a university with no seeded catalog whose own uploads are all
    settled has genuinely nothing to recommend from — that must still be loud."""
    user = await _student_with_uploaded_checklist(
        db,
        "University of Toronto",
        [{"course_code": "CSC148", "course_name": "Intro to CS", "credits": 1.0}],
    )
    _patch_llm(monkeypatch, json.dumps([_rec("CSC148")]))
    with pytest.raises(NoCatalogError):
        await generate_recommendations(user.id, "Winter 2025", "both", None, db)


async def test_uncatalogued_university_can_advise_from_its_own_checklist(
    db, monkeypatch
):
    """And the payoff: a UofT student who uploaded a checklist now gets advice
    grounded in their OWN parsed requirements, with no invented catalog.

    Eligibility is not enforced for these (student-sourced entries carry no
    prerequisites), which is why `catalog_status.verified` stays false — the UI
    is expected to say so rather than imply verified advising.
    """
    user = await _student_with_uploaded_checklist(
        db,
        "University of Toronto",
        [
            {"course_code": "CSC148", "course_name": "Intro to CS", "credits": 1.0},
            {"course_code": "MAT137", "course_name": "Calculus", "credits": 1.0},
            {"course_code": "CSC207", "course_name": "Software Design", "credits": 1.0},
            {"course_code": "CSC209", "course_name": "Systems Programming", "credits": 1.0},
        ],
    )
    _patch_llm(monkeypatch, json.dumps([_rec("CSC209")]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    # Codes come back canonicalized ("CSC209" -> "CSC 209").
    assert [r.course_code for r in recs] == [normalize_course_code("CSC209")]
    # Metadata still comes from the catalog layer, not the model.
    assert recs[0].course_name == "Systems Programming"


async def test_cs_only_catalog_refuses_to_advise_a_psychology_student(db, monkeypatch):
    """Catalogs are built one program document at a time, so they are almost
    never university-wide.

    Ingesting a Computer Science checklist gives York a real catalog — of EECS
    and MATH courses. Because the catalog is keyed on university alone, that
    would otherwise make a York Psychology student "covered": they stop getting
    "no catalog" and start being recommended EECS courses. Confidently wrong is
    worse than blank.
    """
    await _seed_york_catalog(db)  # EECS/MATH only
    user = await _student_with_uploaded_checklist(
        db,
        YORK_UNIVERSITY,
        [
            {"course_code": "AP/PSYC 1010", "course_name": "Introduction to Psychology", "credits": 6.0},
            {"course_code": "AP/PSYC 2030", "course_name": "Statistical Methods I", "credits": 3.0},
            {"course_code": "AP/PSYC 2130", "course_name": "Cognitive Psychology", "credits": 3.0},
        ],
    )
    _patch_llm(monkeypatch, json.dumps([_rec("LE/EECS 2030")]))

    with pytest.raises(NoCoverageError) as excinfo:
        await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert "PSYC" in str(excinfo.value)


async def test_cs_catalog_still_advises_the_cs_student(db, monkeypatch):
    """The coverage guard must not fire for the program the catalog is for."""
    user = await _make_student(db, "above_gate")
    _patch_llm(monkeypatch, json.dumps([_rec("LE/EECS 2030")]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert [r.course_code for r in recs] == ["LE/EECS 2030"]


async def test_coverage_is_not_asserted_for_a_student_with_no_courses(db, monkeypatch):
    """A student who has entered nothing has no subjects to compare, so coverage
    is unknowable — don't refuse on a guess."""
    await _seed_york_catalog(db)
    user = await _make_student(db, "fresh")
    _patch_llm(monkeypatch, json.dumps([_rec("LE/EECS 1019")]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert [r.course_code for r in recs] == ["LE/EECS 1019"]


async def test_uncatalogued_university_fails_loudly_not_silently(db, monkeypatch):
    """The gap this harness was built to find.

    Acadvo invites students at any university, but only seeds a catalog for
    York CS. For everyone else the allowed list renders as "(no catalog courses
    available)", the model has nothing to pick, every code it invents is dropped,
    and the student gets an empty panel indistinguishable from "you need nothing".

    That must be an explicit, non-retryable signal instead.
    """
    user = User(
        id=uuid.uuid4(),
        email=f"uoft-{uuid.uuid4().hex[:8]}@utoronto.ca",
        hashed_password=hash_password("testpass123"),
        full_name="UofT Student",
        university="University of Toronto",
        program="Computer Science",
        start_year=2023,
        expected_graduation_year=2027,
    )
    db.add(user)
    await db.flush()
    db.add(
        DegreeRequirement(
            user_id=user.id, bucket_name="CS Core", credits_required=42.0
        )
    )
    for code, name in [("CSC148", "Intro to CS"), ("MAT137", "Calculus")]:
        db.add(
            Course(
                user_id=user.id,
                course_code=code,
                course_name=name,
                credit_value=1.0,
                status=CourseStatus.completed,
                grade="A",
            )
        )
    await db.commit()

    # The model is never reached, so give it something that would otherwise pass.
    _patch_llm(monkeypatch, json.dumps([_rec("CSC148")]))

    with pytest.raises(NoCatalogError) as excinfo:
        await generate_recommendations(user.id, "Winter 2025", "both", None, db)

    message = str(excinfo.value)
    assert "University of Toronto" in message
    # Says what still works, so the student isn't left thinking the app is broken.
    assert "planner" in message.lower()


async def test_york_student_is_unaffected_by_the_catalog_guard(db, monkeypatch):
    """The guard must not fire for the university that does have a catalog."""
    user = await _make_student(db, "above_gate")
    _patch_llm(monkeypatch, json.dumps([_rec("LE/EECS 2030")]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert [r.course_code for r in recs] == ["LE/EECS 2030"]


async def test_duplicate_codes_collapse_to_one(db, monkeypatch):
    user = await _make_student(db, "above_gate")
    _patch_llm(monkeypatch, MISBEHAVIOURS["duplicated"])
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert len(recs) == 1


# ── Dimension 4: cached requirement rules ────────────────────────────
#
# The research path decides, once, what satisfies a requirement bucket, and the
# decision is cached as `RequirementRule` rows. Everything below asks the same
# question of that layer that the rest of this file asks of the catalog layer:
# **what happens when it is wrong, absent, or disagreed with?**
#
# The validators above must keep running underneath regardless of what any rule
# says — a rule is an opinion about what a course counts for, never a licence to
# recommend a course that does not exist or that the student cannot take.

from app.models.requirement_rule import BASIS_STATED, RequirementRule  # noqa: E402
from app.services.requirement_rules import EXCLUDED, SATISFIES  # noqa: E402

_YORK_SOURCE = [{"uri": "https://calendars.students.yorku.ca/rules", "domain": "yorku.ca"}]


async def _seed_rule(db, *, bucket_name, program="Computer Science", **over):
    row = RequirementRule(
        id=uuid.uuid4(),
        university=YORK_UNIVERSITY,
        program=program,
        bucket_name=bucket_name,
        credits_required=over.pop("credits_required", 42.0),
        allowed_subjects=over.pop("allowed_subjects", []),
        stated_codes=over.pop("stated_codes", []),
        excluded_codes=over.pop("excluded_codes", []),
        excluded_subjects=over.pop("excluded_subjects", []),
        source_quote=over.pop("source_quote", "Quoted from the calendar."),
        basis=over.pop("basis", BASIS_STATED),
        source_urls=over.pop("source_urls", list(_YORK_SOURCE)),
        extracted_at=over.pop("extracted_at", datetime.now(timezone.utc)),
        extracted_by="gemini-2.5-flash",
        **over,
    )
    db.add(row)
    await db.commit()
    return row


RULE_STATES = ("none", "supporting", "excluding")


async def _apply_rule_state(db, rule_state: str):
    if rule_state == "supporting":
        await _seed_rule(
            db,
            bucket_name="Computer Science Core",
            allowed_subjects=["LE/EECS"],
        )
    elif rule_state == "excluding":
        # The university says EECS courses do not satisfy this bucket — the exact
        # situation where a model's confident bucket claim is actively harmful.
        await _seed_rule(
            db,
            bucket_name="Computer Science Core",
            allowed_subjects=["SC/NATS"],
            excluded_subjects=["EECS"],
        )


@pytest.mark.parametrize("rule_state", RULE_STATES)
@pytest.mark.parametrize("misbehaviour", sorted(MISBEHAVIOURS))
async def test_invariants_hold_across_rule_states(rule_state, misbehaviour, db, monkeypatch):
    """Every catalog-layer invariant survives every requirement-rule state.

    A rule must never be able to rescue a fabricated code, un-block a gated
    course, or restore the model's invented credits.
    """
    user = await _make_student(db, "above_gate")
    await _apply_rule_state(db, rule_state)
    _patch_llm(monkeypatch, MISBEHAVIOURS[misbehaviour])

    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)

    await _assert_invariants(recs, user, db, f"rules={rule_state}/{misbehaviour}")


async def test_a_rule_cannot_resurrect_a_fabricated_course(db, monkeypatch):
    """The structural guarantee, checked end to end.

    A researched rule can name a course that does not exist — research is a model
    reading web pages. That must be inert: the rule classifies courses, it does
    not stock the catalog, so the fabricated code is still dropped by the
    catalog validator underneath.
    """
    user = await _make_student(db, "above_gate")
    await _seed_rule(
        db,
        bucket_name="Computer Science Core",
        allowed_subjects=["LE/EECS"],
        stated_codes=["LE/EECS 4040"],  # not in the catalog
    )
    _patch_llm(monkeypatch, json.dumps([_rec("LE/EECS 4040")]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs == [], "a requirement rule introduced a course into recommendations"


async def test_a_rule_cannot_unblock_a_gpa_gated_course(db, monkeypatch):
    """"This counts toward your degree" and "you are allowed to take it" are
    different questions, and the second one is not the rule layer's to answer."""
    user = await _make_student(db, "below_gate")
    await _seed_rule(
        db,
        bucket_name="Computer Science Core",
        allowed_subjects=["LE/EECS"],
        stated_codes=["LE/EECS 2030"],
    )
    _patch_llm(monkeypatch, MISBEHAVIOURS["gpa_gated"])
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs
    for r in recs:
        assert "BLOCKED" in (r.prerequisite_notes or "")
        assert "4.50" in r.prerequisite_notes


async def test_the_model_bucket_claim_is_retracted_when_the_rule_excludes_it(db, monkeypatch):
    """The failure this whole layer exists to prevent.

    The model files LE/EECS 2030 under a bucket the university explicitly says
    EECS courses cannot satisfy. Passing that through tells the student a course
    counts toward their degree when it does not — invisible until their audit.
    """
    user = await _make_student(db, "above_gate")
    await _seed_rule(
        db,
        bucket_name="Computer Science Core",
        allowed_subjects=["SC/NATS"],
        excluded_subjects=["EECS"],
    )
    _patch_llm(
        monkeypatch,
        json.dumps([_rec("LE/EECS 2030", requirement_bucket="Computer Science Core")]),
    )
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.requirement_bucket is None, "an excluded bucket claim survived"
    assert rec.bucket_verdict["outcome"] == EXCLUDED
    assert rec.bucket_verdict["counts"] is False
    # The correction is shown, not silently applied.
    assert "does not count" in rec.bucket_verdict["label"].lower()
    assert rec.bucket_verdict["source_urls"] == [_YORK_SOURCE[0]["uri"]]


async def test_a_supported_bucket_claim_is_kept_and_cited(db, monkeypatch):
    user = await _make_student(db, "above_gate")
    await _seed_rule(
        db,
        bucket_name="Computer Science Core",
        allowed_subjects=["LE/EECS"],
        stated_codes=["LE/EECS 2030"],
    )
    _patch_llm(
        monkeypatch,
        json.dumps([_rec("LE/EECS 2030", requirement_bucket="Computer Science Core")]),
    )
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs[0].requirement_bucket == "Computer Science Core"
    verdict = recs[0].bucket_verdict
    assert verdict["outcome"] == SATISFIES
    assert verdict["certainty"] == "stated"
    assert verdict["source_urls"]


async def test_a_pattern_matched_bucket_claim_is_hedged(db, monkeypatch):
    """The rule was read plainly; this particular course was not named on the
    page. The student is told which of the two they are getting."""
    user = await _make_student(db, "above_gate")
    await _seed_rule(
        db,
        bucket_name="Computer Science Core",
        allowed_subjects=["LE/EECS"],
        basis=BASIS_STATED,
    )
    _patch_llm(
        monkeypatch,
        json.dumps([_rec("LE/EECS 2030", requirement_bucket="Computer Science Core")]),
    )
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    verdict = recs[0].bucket_verdict
    assert verdict["certainty"] == "inferred"
    assert verdict["is_inference"] is True
    assert "Likely" in verdict["label"]
    assert "not a statement from your university" in verdict["label"]


async def test_no_rules_means_no_verdict_not_a_negative_one(db, monkeypatch):
    """An unresearched program must behave exactly as it did before this layer
    existed. Silence is the honest answer, and it must not read as a refusal."""
    user = await _make_student(db, "above_gate")
    _patch_llm(
        monkeypatch,
        json.dumps([_rec("LE/EECS 2030", requirement_bucket="Computer Science Core")]),
    )
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs[0].bucket_verdict is None
    assert recs[0].requirement_bucket == "Computer Science Core"


async def test_another_programs_rules_are_never_applied(db, monkeypatch):
    """Rules are keyed on (university, program) precisely because the catalog is
    not. A Psychology rule at York must not touch a Computer Science student."""
    user = await _make_student(db, "above_gate")
    await _seed_rule(
        db,
        program="Psychology",
        bucket_name="Computer Science Core",
        allowed_subjects=["SC/NATS"],
        excluded_subjects=["EECS"],
    )
    _patch_llm(
        monkeypatch,
        json.dumps([_rec("LE/EECS 2030", requirement_bucket="Computer Science Core")]),
    )
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert recs[0].requirement_bucket == "Computer Science Core"
    assert recs[0].bucket_verdict is None


async def test_research_is_queued_for_an_uncovered_program(db, monkeypatch):
    """Coverage grows from real usage: the student who gets the honest refusal is
    the signal that their program is worth researching. The request must not
    wait for it, and must still raise the same error it always did.
    """
    monkeypatch.setattr("app.research.runner.is_research_enabled", lambda: True)
    user = await _student_with_uploaded_checklist(
        db,
        "University of Toronto",
        [{"course_code": "CSC148", "course_name": "Intro to CS", "credits": 1.0}],
    )
    _patch_llm(monkeypatch, json.dumps([_rec("CSC148")]))

    with pytest.raises(NoCatalogError):
        await generate_recommendations(user.id, "Winter 2025", "both", None, db)

    from app.research.runner import get_job

    job = await get_job(db, "University of Toronto", "Computer Science")
    assert job is not None and job.status == "pending"


async def test_a_failure_to_queue_research_never_breaks_advising(db, monkeypatch):
    """Enqueueing is a side errand. If it throws, the student still gets advice."""
    monkeypatch.setattr("app.research.runner.is_research_enabled", lambda: True)

    async def _explode(db_, university, program):
        raise RuntimeError("queue is on fire")

    monkeypatch.setattr("app.research.runner.needs_research", _explode)

    user = await _make_student(db, "above_gate")
    _patch_llm(monkeypatch, json.dumps([_rec("LE/EECS 2030")]))
    recs = await generate_recommendations(user.id, "Winter 2025", "both", None, db)
    assert [r.course_code for r in recs] == ["LE/EECS 2030"]
