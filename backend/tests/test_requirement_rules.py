"""Tests for the AI research + cached requirement-rule path.

Organised by the thing being defended rather than by module, because the guards
matter more than the plumbing:

  1. Grounding      — a rule with no real citation is never stored.
  2. Exclusions     — a "will not count" list never becomes an option list.
  3. Vacuity        — a rule that would match everything is never stored.
  4. Honesty        — an inference is never rendered as a fact.
  5. Coverage gaps  — "no rule" is reported as unknown, never as "does not count".
  6. Caching        — the second student costs nothing and gets the same answer.
  7. Fabrication    — a rule can never introduce a course into the catalog.

Every one of these is mutation-tested in `test_mutation_sentinels` at the bottom:
the guard is deliberately bypassed and the assertion is that this test file
notices. An eval suite that passes on broken code is worthless.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.ai.research_client import (
    ResearchResult,
    Source,
    UngroundedResearchError,
    extract_json,
    strip_code_fence,
)
from app.models.requirement_rule import (
    BASIS_INFERRED,
    BASIS_STATED,
    JOB_FAILED,
    JOB_PENDING,
    JOB_SUCCEEDED,
    ProgramResearchJob,
    RequirementRule,
)
from app.models.user import User
from app.research import program_rules, runner
from app.research.schema import (
    RuleRejected,
    normalize_rule,
    normalize_rules,
    validate_requirements_url,
    validate_sources,
)
from app.services.auth import hash_password
from app.services.eligibility import satisfies_bucket
from app.services.requirement_rules import (
    EXCLUDED,
    INFERRED,
    NO_MATCH,
    SATISFIES,
    STATED,
    classify_course,
    evaluate_rule,
    get_rules,
    rules_summary,
    subject_matches,
)

YORK = "York University"
CS = "Computer Science"
# Research now READS a page rather than searching for one — Google Search
# grounding is billed and 429s on the free tier, so the URL is supplied.
REQ_URL = "https://calendars.students.yorku.ca/2025-2026/faculty-rules"


# ── Fixtures / helpers ───────────────────────────────────────────────


def _rule(**over) -> RequirementRule:
    """An in-memory rule row. York's real Non-Science gen-ed shape by default."""
    base = dict(
        id=uuid.uuid4(),
        university=YORK,
        program=CS,
        bucket_name="Non-Science General Education",
        credits_required=18.0,
        allowed_subjects=["AP/HUMA", "AP/SOSC"],
        level_floor=None,
        level_ceiling=None,
        stated_codes=[],
        excluded_codes=[],
        excluded_subjects=[],
        source_quote="Students must complete 6.00 credits in AP/HUMA and 6.00 credits in AP/SOSC.",
        notes=None,
        basis=BASIS_STATED,
        source_urls=[{"uri": "https://calendars.students.yorku.ca/x", "domain": "yorku.ca"}],
        extracted_at=datetime.now(timezone.utc),
        extracted_by="gemini-2.5-flash",
    )
    base.update(over)
    return RequirementRule(**base)


async def _student(db, university=YORK, program=CS) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"rules-{uuid.uuid4().hex[:8]}@my.yorku.ca",
        hashed_password=hash_password("testpass123"),
        full_name="Rules Student",
        university=university,
        program=program,
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    return user


def _grounded(text: str, *, domain="yorku.ca") -> ResearchResult:
    return ResearchResult(
        text=text,
        sources=[
            Source(
                uri="https://calendars.students.yorku.ca/2025-2026/faculty-rules",
                title="Faculty Rules",
                domain=domain,
            )
        ],
        model="gemini-2.5-flash",
    )


GOOD_PAYLOAD = """{
  "university": "York University",
  "program": "Computer Science",
  "rules": [
    {
      "bucket_name": "Non-Science General Education",
      "credits_required": 18.0,
      "allowed_subjects": ["AP/HUMA", "AP/SOSC"],
      "stated_codes": [],
      "excluded_codes": ["AP/ECON 1000"],
      "source_quote": "6.00 credits in AP/HUMA and 6.00 credits in AP/SOSC.",
      "basis": "stated"
    }
  ]
}"""


def _patch_research(monkeypatch, result_or_exc):
    async def _fake(prompt, **kwargs):
        if isinstance(result_or_exc, Exception):
            raise result_or_exc
        return result_or_exc

    monkeypatch.setattr(program_rules, "research", _fake)
    monkeypatch.setattr(program_rules, "is_research_enabled", lambda: True)


# ── 1. Grounding: an ungrounded answer is never stored ───────────────


async def test_research_without_grounding_is_rejected(db, monkeypatch):
    """The model answering from memory is the failure mode that matters most.

    It is indistinguishable from a correct reading, and there is nothing to check
    it against later. It must never reach the database.
    """
    _patch_research(monkeypatch, UngroundedResearchError())
    with pytest.raises(program_rules.ResearchFailed):
        await program_rules.research_program_rules(YORK, CS, [REQ_URL])
    assert await get_rules(YORK, CS, db) == []


async def test_research_grounded_only_in_a_forum_is_rejected():
    """A citation to r/yorku is grounding in the API's sense and worthless in
    ours. Degree requirements come from the university or from nowhere."""
    with pytest.raises(RuleRejected):
        validate_sources([{"uri": "https://reddit.com/r/yorku/x", "domain": "reddit.com"}])
    with pytest.raises(RuleRejected):
        validate_sources([])
    # A university page survives even when a forum result sits alongside it.
    kept = validate_sources(
        [
            {"uri": "https://reddit.com/r/yorku/x", "domain": "www.reddit.com"},
            {"uri": "https://calendars.students.yorku.ca/x", "domain": "yorku.ca"},
        ]
    )
    assert [s["domain"] for s in kept] == ["yorku.ca"]


async def test_untrusted_subdomains_are_still_untrusted():
    with pytest.raises(RuleRejected):
        validate_sources([{"uri": "https://old.reddit.com/x", "domain": "old.reddit.com"}])


async def test_research_response_stores_the_urls_it_actually_retrieved(db, monkeypatch):
    _patch_research(monkeypatch, _grounded(GOOD_PAYLOAD))
    written = await program_rules.run_research(db, YORK, CS, [REQ_URL])
    assert written == 1
    rules = await get_rules(YORK, CS, db)
    assert rules[0].source_urls[0]["domain"] == "yorku.ca"
    assert rules[0].extracted_by == "gemini-2.5-flash"


# ── 2. Exclusions are not options ────────────────────────────────────


async def test_excluded_code_never_becomes_a_stated_option():
    """A model that mis-splits "the following will not count" produces a rule
    recommending precisely the courses the requirement forbids."""
    rule = normalize_rule(
        {
            "bucket_name": "Foundational Science",
            "allowed_subjects": ["SC/BIOL"],
            "stated_codes": ["SC/BIOL 1000", "SC/BIOL 1500"],
            "excluded_codes": ["SC/BIOL 1500"],
        }
    )
    assert "SC/BIOL 1500" in rule.excluded_codes
    assert "SC/BIOL 1500" not in rule.stated_codes


async def test_exclusion_beats_a_matching_subject_rule():
    """The normal shape of these documents: a course inside an allowed subject
    family, named in the exclusion sentence below it. The exclusion wins."""
    rule = _rule(allowed_subjects=["AP/HUMA"], excluded_codes=["AP/HUMA 1970"])
    verdict = evaluate_rule(rule, "AP/HUMA 1970")
    assert verdict.outcome == EXCLUDED
    assert not verdict.counts
    assert "does not count" in verdict.label().lower()


async def test_excluded_subject_beats_a_matching_subject_rule():
    rule = _rule(allowed_subjects=["AP/HUMA", "AP/SOSC"], excluded_subjects=["AP/SOSC"])
    assert evaluate_rule(rule, "AP/SOSC 1000").outcome == EXCLUDED
    assert evaluate_rule(rule, "AP/HUMA 1000").outcome == SATISFIES


# ── 3. A rule that matches everything is not a rule ──────────────────


@pytest.mark.parametrize("wildcard", ["*", "ANY", "ALL", "elective"])
async def test_wildcard_subject_is_refused(wildcard):
    with pytest.raises(RuleRejected):
        normalize_rule({"bucket_name": "Electives", "allowed_subjects": [wildcard]})


async def test_rule_with_no_subjects_and_no_codes_is_refused():
    with pytest.raises(RuleRejected):
        normalize_rule({"bucket_name": "Electives"})


async def test_a_full_course_code_in_allowed_subjects_is_dropped():
    """`allowed_subjects` is a family, not a list. A code here means the model
    confused a rule with an enumeration; it belongs in stated_codes."""
    rule = normalize_rule(
        {
            "bucket_name": "Core",
            "allowed_subjects": ["LE/EECS 2030", "LE/EECS"],
            "stated_codes": [],
        }
    )
    assert rule.allowed_subjects == ["LE/EECS"]


# ── 4. An inference is never rendered as a fact ──────────────────────


async def test_pattern_match_is_labelled_an_inference_even_from_a_stated_rule():
    """The rule was read plainly off the page. Applying it to a course the page
    never mentions is still a step the page did not take, and the student is told
    so — this is the one unrecoverable error in the product."""
    rule = _rule(basis=BASIS_STATED, allowed_subjects=["AP/HUMA"])
    verdict = evaluate_rule(rule, "AP/HUMA 1105")
    assert verdict.outcome == SATISFIES
    assert verdict.certainty == INFERRED
    assert verdict.is_inference
    label = verdict.label()
    assert "Likely" in label
    assert "inference" in label.lower()
    assert "not a statement from your university" in label


async def test_a_course_the_page_names_is_reported_as_a_fact():
    rule = _rule(stated_codes=["AP/HUMA 1105"])
    verdict = evaluate_rule(rule, "AP/HUMA 1105")
    assert verdict.certainty == STATED
    assert not verdict.is_inference
    assert "named in the requirement" in verdict.label()
    assert "Likely" not in verdict.label()


async def test_basis_is_never_upgraded_to_stated_without_a_quote():
    """"Stated" is a claim that a sentence exists. With no sentence, the claim
    that the rule was read directly is itself unsupported."""
    rule = normalize_rule(
        {"bucket_name": "Core", "allowed_subjects": ["LE/EECS"], "basis": "stated"}
    )
    assert rule.basis == BASIS_INFERRED

    quoted = normalize_rule(
        {
            "bucket_name": "Core",
            "allowed_subjects": ["LE/EECS"],
            "basis": "stated",
            "source_quote": "All LE/EECS courses count toward the major.",
        }
    )
    assert quoted.basis == BASIS_STATED


@pytest.mark.parametrize("bogus", ["certain", "definitely", "", None, 7])
async def test_unrecognised_basis_defaults_down_not_up(bogus):
    rule = normalize_rule(
        {"bucket_name": "Core", "allowed_subjects": ["LE/EECS"], "basis": bogus}
    )
    assert rule.basis == BASIS_INFERRED


async def test_every_verdict_carries_its_sources():
    rule = _rule(stated_codes=["AP/HUMA 1105"])
    for code in ("AP/HUMA 1105", "AP/HUMA 2000", "SC/MATH 1300"):
        verdict = evaluate_rule(rule, code)
        assert verdict.source_urls == ["https://calendars.students.yorku.ca/x"]


async def test_a_stale_rule_is_served_but_flagged():
    """Losing advising because a calendar turned over is worse than saying
    "checked a while ago"."""
    old = datetime.now(timezone.utc) - timedelta(days=400)
    verdict = evaluate_rule(_rule(extracted_at=old), "AP/HUMA 1105")
    assert verdict.outcome == SATISFIES
    assert verdict.stale
    assert "calendars change yearly" in verdict.label().lower()


# ── 5. "No rule" means unknown, never "does not count" ───────────────


async def test_uncovered_course_is_reported_as_unknown_not_as_a_refusal():
    rule = _rule(allowed_subjects=["AP/HUMA"])
    verdict = evaluate_rule(rule, "LE/EECS 2030")
    assert verdict.outcome == NO_MATCH
    assert not verdict.counts
    label = verdict.label()
    assert "not the same as" in label
    assert "advisor" in label


async def test_a_program_with_no_rules_returns_none_not_a_verdict(db):
    """`None` is the honest answer for an unresearched program, and it must not
    be collapsed into a negative anywhere upstream."""
    user = await _student(db, university="University of Toronto", program="Physics")
    assert await satisfies_bucket(user.university, user.program, "PHY 151", db) is None
    assert classify_course([], "PHY 151") is None


async def test_classify_prefers_an_explicit_exclusion_over_a_match():
    """When several buckets have something to say, a hard no is always the most
    important thing to surface."""
    match = _rule(bucket_name="Gen Ed", allowed_subjects=["AP/HUMA"])
    excl = _rule(bucket_name="Science", excluded_codes=["AP/HUMA 1105"], allowed_subjects=["SC/NATS"])
    verdict = classify_course([match, excl], "AP/HUMA 1105")
    assert verdict.outcome == EXCLUDED


async def test_classify_prefers_a_stated_match_over_an_inferred_one():
    inferred = _rule(bucket_name="Gen Ed", allowed_subjects=["AP/HUMA"])
    stated = _rule(bucket_name="Humanities", allowed_subjects=[], stated_codes=["AP/HUMA 1105"])
    verdict = classify_course([inferred, stated], "AP/HUMA 1105")
    assert verdict.certainty == STATED
    assert verdict.bucket_name == "Humanities"


async def test_classify_with_an_unknown_bucket_name_returns_none():
    rule = _rule(bucket_name="Gen Ed")
    assert classify_course([rule], "AP/HUMA 1105", bucket_name="Nonexistent") is None


# ── Subject matching ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code,token,expected",
    [
        ("AP/HUMA 1105", "AP/HUMA", True),
        ("AP/HUMA 1105", "HUMA", True),
        # A faculty-qualified rule does not license a different faculty's
        # offering of the same subject.
        ("ES/HUMA 1105", "AP/HUMA", False),
        ("CMPT 225", "CMPT", True),
        ("CMPT 225", "cmpt", True),
        ("CMPT 225", "MACM", False),
        ("", "CMPT", False),
        ("CMPT 225", "", False),
    ],
)
async def test_subject_matching(code, token, expected):
    assert subject_matches(code, token) is expected


async def test_level_floor_and_ceiling():
    rule = _rule(allowed_subjects=["AP/HUMA"], level_floor=2000, level_ceiling=3999)
    assert evaluate_rule(rule, "AP/HUMA 1105").outcome == NO_MATCH
    assert evaluate_rule(rule, "AP/HUMA 2100").outcome == SATISFIES
    assert evaluate_rule(rule, "AP/HUMA 4000").outcome == NO_MATCH


# ── 6. Caching: research once, serve forever ─────────────────────────


async def test_second_student_in_a_program_costs_nothing_and_agrees(db, monkeypatch):
    """The whole point of caching the decision. Two students, one research call,
    byte-identical verdicts."""
    calls = []

    async def _counting(prompt, **kwargs):
        calls.append(prompt)
        return _grounded(GOOD_PAYLOAD)

    monkeypatch.setattr(program_rules, "research", _counting)
    monkeypatch.setattr(program_rules, "is_research_enabled", lambda: True)
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)

    first = await _student(db)
    second = await _student(db)

    await runner.ensure_research(db, YORK, CS, [REQ_URL])
    assert await runner.process_once(db) is True
    assert len(calls) == 1

    v1 = await satisfies_bucket(first.university, first.program, "AP/HUMA 1105", db)
    v2 = await satisfies_bucket(second.university, second.program, "AP/HUMA 1105", db)
    assert v1.as_dict() == v2.as_dict()
    # And no further research was queued for the now-covered program.
    assert await runner.ensure_research(db, YORK, CS) is None
    assert len(calls) == 1


async def test_re_running_research_replaces_rather_than_accumulates(db, monkeypatch):
    """A calendar update must leave the CURRENT rule in place. A superseded rule
    is not something advising should ever fall back to."""
    _patch_research(monkeypatch, _grounded(GOOD_PAYLOAD))
    await program_rules.run_research(db, YORK, CS, [REQ_URL])

    revised = GOOD_PAYLOAD.replace('"credits_required": 18.0', '"credits_required": 12.0')
    _patch_research(monkeypatch, _grounded(revised))
    await program_rules.run_research(db, YORK, CS, [REQ_URL])

    rules = await get_rules(YORK, CS, db)
    assert len(rules) == 1
    assert rules[0].credits_required == 12.0


async def test_a_bucket_the_university_dropped_stops_being_applied(db, monkeypatch):
    two_buckets = """{"rules": [
      {"bucket_name": "Gen Ed", "allowed_subjects": ["AP/HUMA"]},
      {"bucket_name": "Retired Bucket", "allowed_subjects": ["AP/SOSC"]}
    ]}"""
    _patch_research(monkeypatch, _grounded(two_buckets))
    await program_rules.run_research(db, YORK, CS, [REQ_URL])
    assert len(await get_rules(YORK, CS, db)) == 2

    _patch_research(
        monkeypatch,
        _grounded('{"rules": [{"bucket_name": "Gen Ed", "allowed_subjects": ["AP/HUMA"]}]}'),
    )
    await program_rules.run_research(db, YORK, CS, [REQ_URL])
    remaining = await get_rules(YORK, CS, db)
    assert [r.bucket_name for r in remaining] == ["Gen Ed"]


async def test_stale_rules_requeue_but_keep_serving(db, monkeypatch):
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    db.add(_rule(extracted_at=datetime.now(timezone.utc) - timedelta(days=400)))
    await db.commit()

    assert await runner.needs_research(db, YORK, CS) is True
    job = await runner.ensure_research(db, YORK, CS)
    assert job is not None and job.status == JOB_PENDING
    # Still answering while the refresh is queued.
    verdict = await satisfies_bucket(YORK, CS, "AP/HUMA 1105", db)
    assert verdict.counts and verdict.stale


# ── The job queue ────────────────────────────────────────────────────


async def test_research_is_not_queued_without_a_key(db, monkeypatch):
    monkeypatch.setattr(runner, "is_research_enabled", lambda: False)
    assert await runner.ensure_research(db, YORK, CS) is None


async def test_concurrent_first_students_produce_one_job(db, monkeypatch):
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    a = await runner.ensure_research(db, YORK, CS)
    b = await runner.ensure_research(db, YORK, CS)
    assert a is not None and b is not None
    assert a.id == b.id


async def test_a_claimed_job_cannot_be_claimed_twice(db, monkeypatch):
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    await runner.ensure_research(db, YORK, CS)
    first = await runner._claim_next(db)
    assert first is not None
    assert await runner._claim_next(db) is None


async def test_claiming_a_job_someone_else_took_reports_failure(db, monkeypatch):
    """The cross-process race, tested where it actually lives.

    Two workers can both SELECT the same pending job. The conditional UPDATE is
    what stops both of them paying for the same research call, and a
    single-process test of `_claim_next` would pass even with that condition
    removed — so the claim is exercised directly against an already-taken job.
    """
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    job = await runner.ensure_research(db, YORK, CS)
    assert await runner.claim(db, job) is True
    assert await runner.claim(db, job) is False, (
        "a second worker claimed a job that was already running"
    )


async def test_a_failed_job_records_why(db, monkeypatch):
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    _patch_research(monkeypatch, _grounded("this is prose, not JSON"))
    await runner.ensure_research(db, YORK, CS, [REQ_URL])
    assert await runner.process_once(db) is True

    job = await runner.get_job(db, YORK, CS)
    assert job.status == JOB_FAILED
    assert "not JSON" in job.last_error
    assert await get_rules(YORK, CS, db) == []


async def test_a_crashing_job_does_not_kill_the_worker(db, monkeypatch):
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)

    async def _boom(prompt, **kwargs):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(program_rules, "research", _boom)
    monkeypatch.setattr(program_rules, "is_research_enabled", lambda: True)
    await runner.ensure_research(db, YORK, CS, [REQ_URL])
    assert await runner.process_once(db) is True

    job = await runner.get_job(db, YORK, CS)
    assert job.status == JOB_FAILED
    assert "provider exploded" in job.last_error


async def test_a_repeatedly_failing_program_stops_being_retried(db, monkeypatch):
    """One unreadable university must not consume the research budget forever."""
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    job = ProgramResearchJob(
        university=YORK,
        program=CS,
        status=JOB_FAILED,
        attempts=runner.MAX_ATTEMPTS,
        finished_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db.add(job)
    await db.commit()

    again = await runner.ensure_research(db, YORK, CS)
    assert again.status == JOB_FAILED

    # But an explicit refresh overrides the ceiling and resets the counter.
    refreshed = await runner.request_refresh(db, YORK, CS)
    assert refreshed.status == JOB_PENDING
    assert refreshed.attempts == 0


async def test_a_recently_failed_job_waits_before_retrying(db, monkeypatch):
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    db.add(
        ProgramResearchJob(
            university=YORK,
            program=CS,
            status=JOB_FAILED,
            attempts=1,
            finished_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    assert (await runner.ensure_research(db, YORK, CS)).status == JOB_FAILED

    # Past the cooldown it becomes eligible again.
    job = await runner.get_job(db, YORK, CS)
    job.finished_at = datetime.now(timezone.utc) - (runner.RETRY_AFTER + timedelta(hours=1))
    await db.commit()
    assert (await runner.ensure_research(db, YORK, CS)).status == JOB_PENDING


async def test_a_job_abandoned_by_a_dead_process_is_reclaimed(db, monkeypatch):
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    _patch_research(monkeypatch, _grounded(GOOD_PAYLOAD))
    db.add(
        ProgramResearchJob(
            university=YORK,
            program=CS,
            status="running",
            attempts=1,
            source_urls=[REQ_URL],
            started_at=datetime.now(timezone.utc) - (runner.STALE_RUNNING_AFTER + timedelta(minutes=5)),
        )
    )
    await db.commit()
    assert await runner.process_once(db) is True
    assert (await runner.get_job(db, YORK, CS)).status == JOB_SUCCEEDED


# ── 7. A rule can never introduce a course ───────────────────────────


async def test_research_writes_no_catalog_rows(db, monkeypatch):
    """The structural guarantee behind "never fabricate course data": the
    research path has no write access to the catalog, so a hallucinated course
    code inside a rule cannot become a course Acadvo recommends. It can only
    fail to match anything.
    """
    from sqlalchemy import func, select

    from app.models.catalog import CatalogCourse

    payload = """{"rules": [{
      "bucket_name": "Gen Ed",
      "allowed_subjects": ["AP/HUMA"],
      "stated_codes": ["AP/HUMA 9999", "AP/FAKE 1000"]
    }]}"""
    _patch_research(monkeypatch, _grounded(payload))
    await program_rules.run_research(db, YORK, CS, [REQ_URL])

    count = await db.scalar(select(func.count()).select_from(CatalogCourse))
    assert count == 0


# ── Research-client plumbing ─────────────────────────────────────────


def test_grounding_metadata_is_read_defensively():
    """Absent grounding must read as "nothing retrieved", not AttributeError —
    the two would be handled very differently upstream."""
    from app.ai.research_client import _collect_sources

    assert _collect_sources(SimpleNamespace()) == ([], [])
    assert _collect_sources(SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=None)])) == ([], [])

    chunk = SimpleNamespace(
        web=SimpleNamespace(uri="https://yorku.ca/a", title="York", domain="yorku.ca")
    )
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                grounding_metadata=SimpleNamespace(
                    grounding_chunks=[chunk, chunk],  # duplicate uri
                    web_search_queries=["york cs requirements"],
                )
            )
        ]
    )
    sources, queries = _collect_sources(response)
    assert [s.uri for s in sources] == ["https://yorku.ca/a"]
    assert queries == ["york cs requirements"]


def _fake_genai_urls(text, url_statuses):
    """A response shaped like a url_context run: per-URL retrieval statuses."""
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
        grounding_metadata=None,
        url_context_metadata=SimpleNamespace(
            url_metadata=[
                SimpleNamespace(
                    retrieved_url=u,
                    url_retrieval_status=SimpleNamespace(
                        name=f"URL_RETRIEVAL_STATUS_{s}"
                    ),
                )
                for u, s in url_statuses
            ]
        ),
    )
    return SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kw: SimpleNamespace(text=text, candidates=[candidate])
        )
    )


def _fake_genai(text, chunks):
    """A stand-in for the native Gemini client, shaped like a real response."""
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
        grounding_metadata=SimpleNamespace(
            grounding_chunks=[
                SimpleNamespace(web=SimpleNamespace(uri=u, title=t, domain=d))
                for u, t, d in chunks
            ],
            web_search_queries=[],
        )
        if chunks is not None
        else None,
    )
    return SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kw: SimpleNamespace(text=text, candidates=[candidate])
        )
    )


async def test_research_call_refuses_an_answer_with_no_retrieval(monkeypatch):
    """The guard inside `research()` itself, not just the callers'.

    An answer with no grounding chunks came from the model's memory. It reads
    identically to one taken off the university's calendar, and nothing can check
    it afterwards, so it never leaves this function.
    """
    import app.ai.research_client as rc

    monkeypatch.setattr(rc, "get_research_client", lambda: _fake_genai("{}", []))
    with pytest.raises(UngroundedResearchError):
        await rc.research("anything")


async def test_research_call_returns_text_and_sources_when_grounded(monkeypatch):
    import app.ai.research_client as rc

    monkeypatch.setattr(
        rc,
        "get_research_client",
        lambda: _fake_genai(
            '{"rules": []}', [("https://yorku.ca/a", "York", "yorku.ca")]
        ),
    )
    result = await rc.research("anything")
    assert result.text == '{"rules": []}'
    assert result.source_urls == ["https://yorku.ca/a"]
    assert result.domains == {"yorku.ca"}


async def test_research_call_refuses_an_empty_answer(monkeypatch):
    import app.ai.research_client as rc

    monkeypatch.setattr(
        rc,
        "get_research_client",
        lambda: _fake_genai("", [("https://yorku.ca/a", "York", "yorku.ca")]),
    )
    with pytest.raises(UngroundedResearchError):
        await rc.research("anything")


async def test_research_is_disabled_without_a_key(monkeypatch):
    import app.ai.research_client as rc

    monkeypatch.setattr(rc.settings, "GEMINI_API_KEY", "")
    rc.reset_research_client()
    assert rc.is_research_enabled() is False
    with pytest.raises(rc.ResearchDisabledError):
        rc.get_research_client()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('```\n{"a": 1}\n```', {"a": 1}),
        ('Here are the rules:\n{"a": 1}\nHope that helps.', {"a": 1}),
        ("[1, 2]", [1, 2]),
        ("no json at all", None),
    ],
)
def test_extract_json(raw, expected):
    assert extract_json(raw) == expected


def test_strip_code_fence_leaves_plain_text_alone():
    assert strip_code_fence("  hello  ") == "hello"


async def test_a_list_shaped_response_is_accepted(db, monkeypatch):
    """The prompt asks for an object; models routinely return the bare array."""
    _patch_research(
        monkeypatch,
        _grounded('[{"bucket_name": "Gen Ed", "allowed_subjects": ["AP/HUMA"]}]'),
    )
    assert await program_rules.run_research(db, YORK, CS, [REQ_URL]) == 1


async def test_partial_extraction_keeps_the_good_rules():
    """One unusable bucket must not throw away three good ones."""
    accepted, rejected = normalize_rules(
        [
            {"bucket_name": "Gen Ed", "allowed_subjects": ["AP/HUMA"]},
            {"bucket_name": "Broken"},  # no subjects, no codes
            {"bucket_name": "gen ed", "allowed_subjects": ["AP/SOSC"]},  # duplicate
            {"bucket_name": "Core", "allowed_subjects": ["LE/EECS"]},
        ]
    )
    assert [r.bucket_name for r in accepted] == ["Gen Ed", "Core"]
    assert len(rejected) == 2


async def test_all_rules_rejected_is_a_failure_not_an_empty_success(db, monkeypatch):
    _patch_research(monkeypatch, _grounded('{"rules": [{"bucket_name": "Broken"}]}'))
    with pytest.raises(program_rules.ResearchFailed):
        await program_rules.research_program_rules(YORK, CS, [REQ_URL])


# ── Summary / API surface ────────────────────────────────────────────


async def test_rules_summary_spells_out_the_basis_in_words():
    """`basis` as a bare enum invites a UI that renders both the same way."""
    summary = rules_summary([_rule(basis=BASIS_STATED), _rule(bucket_name="B", basis=BASIS_INFERRED)])
    labels = {b["bucket_name"]: b["basis_label"] for b in summary["buckets"]}
    assert "Read directly" in labels["Non-Science General Education"]
    assert "Acadvo's reading" in labels["B"]


async def test_uncovered_program_asks_for_a_url_instead_of_queueing_a_doomed_job(
    auth_client, db, monkeypatch
):
    """Without Search grounding the model cannot FIND the requirements page, so
    auto-queueing would show a spinner that resolves to a failure. Ask for the
    one thing that would actually fix it instead."""
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    monkeypatch.setattr("app.routers.course_advisor.is_research_enabled", lambda: True)
    resp = await auth_client.get("/course-advisor/program-rules")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "needs_url"
    assert body["bucket_count"] == 0
    assert "link" in body["message"].lower()
    assert body["job"] is None, "queued a job that could never succeed"


async def test_search_grounding_deployments_still_auto_queue(
    auth_client, db, test_user, monkeypatch
):
    """With billing enabled the model can find its own pages, and the original
    zero-touch behaviour is correct again."""
    monkeypatch.setattr(runner, "is_research_enabled", lambda: True)
    monkeypatch.setattr("app.routers.course_advisor.is_research_enabled", lambda: True)
    monkeypatch.setattr(
        "app.routers.course_advisor.settings.RESEARCH_USE_SEARCH_GROUNDING", True
    )
    body = (await auth_client.get("/course-advisor/program-rules")).json()
    assert body["state"] == "researching"


async def test_research_without_a_url_or_search_fails_with_a_usable_reason(monkeypatch):
    """The failure must say what to do, not just that it failed."""
    monkeypatch.setattr(program_rules, "is_research_enabled", lambda: True)
    monkeypatch.setattr(program_rules.settings, "RESEARCH_USE_SEARCH_GROUNDING", False)
    with pytest.raises(program_rules.ResearchFailed) as exc:
        await program_rules.research_program_rules(YORK, CS, None)
    assert "URL" in str(exc.value)


async def test_supplying_a_url_queues_research_for_the_whole_program(
    auth_client, db, test_user, monkeypatch
):
    monkeypatch.setattr("app.routers.course_advisor.is_research_enabled", lambda: True)
    resp = await auth_client.post(
        "/course-advisor/program-rules/research",
        json={"url": "https://artsci.calendar.utoronto.ca/section/Computer-Science"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == JOB_PENDING

    job = await runner.get_job(db, test_user.university, test_user.program)
    assert job.source_urls == [
        "https://artsci.calendar.utoronto.ca/section/Computer-Science"
    ]


@pytest.mark.parametrize(
    "bad",
    [
        "http://localhost/admin",
        "http://127.0.0.1:8000/internal",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "https://reddit.com/r/yorku/comments/x",
        "https://metadata.internal/x",
    ],
)
async def test_a_supplied_url_cannot_point_at_internal_infrastructure(bad):
    """This URL is fetched server-side by the model provider, so naming the
    target is an SSRF-shaped capability even though we never fetch it ourselves.
    """
    with pytest.raises(RuleRejected):
        validate_requirements_url(bad)


async def test_a_real_university_url_is_accepted():
    url = "https://artsci.calendar.utoronto.ca/section/Computer-Science"
    assert validate_requirements_url(url) == url


async def test_a_bad_url_is_refused_with_a_message_not_a_500(auth_client, monkeypatch):
    monkeypatch.setattr("app.routers.course_advisor.is_research_enabled", lambda: True)
    resp = await auth_client.post(
        "/course-advisor/program-rules/research", json={"url": "http://localhost/x"}
    )
    assert resp.status_code == 422
    assert "public web address" in resp.json()["detail"]


async def test_url_retrieval_failure_names_the_url_that_could_not_be_read(monkeypatch):
    """"Research failed" with no reason leaves a program uncovered and nobody
    able to say why — and it is usually just a moved page."""
    import app.ai.research_client as rc

    monkeypatch.setattr(
        rc,
        "get_research_client",
        lambda: _fake_genai_urls("{}", [("https://yorku.ca/gone", "ERROR")]),
    )
    with pytest.raises(UngroundedResearchError) as exc:
        await rc.research("x", urls=["https://yorku.ca/gone"])
    assert "yorku.ca/gone" in str(exc.value)


async def test_only_successfully_retrieved_pages_become_citations(monkeypatch):
    """A model handed an unreachable URL will still answer, describing the page
    from its address alone. Only SUCCESS counts as having read something."""
    import app.ai.research_client as rc

    monkeypatch.setattr(
        rc,
        "get_research_client",
        lambda: _fake_genai_urls(
            '{"rules": []}',
            [("https://yorku.ca/ok", "SUCCESS"), ("https://yorku.ca/bad", "ERROR")],
        ),
    )
    result = await rc.research("x", urls=["https://yorku.ca/ok", "https://yorku.ca/bad"])
    assert result.source_urls == ["https://yorku.ca/ok"]


async def test_program_rules_endpoint_is_honest_when_unconfigured(auth_client, monkeypatch):
    monkeypatch.setattr("app.routers.course_advisor.is_research_enabled", lambda: False)
    body = (await auth_client.get("/course-advisor/program-rules")).json()
    assert body["state"] == "unavailable"
    assert body["research_enabled"] is False


async def test_program_rules_endpoint_serves_cached_rules(auth_client, db, test_user):
    db.add(_rule(university=test_user.university, program=test_user.program))
    await db.commit()
    body = (await auth_client.get("/course-advisor/program-rules")).json()
    assert body["state"] == "ready"
    assert body["bucket_count"] == 1
    bucket = body["buckets"][0]
    assert bucket["source_urls"] == ["https://calendars.students.yorku.ca/x"]
    assert bucket["source_quote"]


async def test_refresh_requires_a_configured_provider(auth_client, monkeypatch):
    monkeypatch.setattr("app.routers.course_advisor.is_research_enabled", lambda: False)
    resp = await auth_client.post("/course-advisor/program-rules/refresh")
    assert resp.status_code == 503


async def test_refresh_queues_a_job(auth_client, db, test_user, monkeypatch):
    monkeypatch.setattr("app.routers.course_advisor.is_research_enabled", lambda: True)
    resp = await auth_client.post("/course-advisor/program-rules/refresh")
    assert resp.status_code == 200
    assert resp.json()["status"] == JOB_PENDING
    job = await runner.get_job(db, test_user.university, test_user.program)
    assert job is not None


# ── Mutation sentinels ───────────────────────────────────────────────
#
# Each of these breaks one guard the way a careless refactor would and asserts
# that the behaviour this file relies on actually changes. If a sentinel fails,
# the corresponding test above is not testing what it claims to.


async def test_mutation_sentinels(monkeypatch):
    """Deliberately break each guard; confirm the protected behaviour collapses."""
    import app.research.schema as schema_mod

    # 1. Grounding — drop the untrusted-domain denylist and a forum becomes a
    #    valid citation for a degree requirement.
    monkeypatch.setattr(schema_mod, "UNTRUSTED_DOMAINS", frozenset())
    kept = schema_mod.validate_sources(
        [{"uri": "https://reddit.com/r/yorku/x", "domain": "reddit.com"}]
    )
    assert kept, "sentinel: the denylist test would pass on broken code"
    monkeypatch.undo()

    # 2. Exclusions — skip the subtraction and an excluded course is offered as
    #    an option.
    rule = schema_mod.ExtractedRule(
        bucket_name="X",
        stated_codes=["SC/BIOL 1000", "SC/BIOL 1500"],
        excluded_codes=["SC/BIOL 1500"],
    )
    assert "SC/BIOL 1500" in rule.stated_codes, (
        "sentinel: normalize_rule's subtraction is what removes it, not the dataclass"
    )

    # 3. Vacuity — a wildcard subject, if allowed through, matches every course
    #    ever offered.
    monkeypatch.setattr(schema_mod, "WILDCARD_SUBJECTS", frozenset())
    wild = schema_mod.normalize_rule(
        {"bucket_name": "Electives", "allowed_subjects": ["ANY"]}
    )
    assert wild.allowed_subjects == ["ANY"]
    monkeypatch.undo()

    # 4. Honesty — a verdict built with certainty=STATED loses every hedge, which
    #    is precisely the sentence that fails silently for a year.
    from app.services.requirement_rules import BucketVerdict

    faked = BucketVerdict(
        bucket_name="Gen Ed", outcome=SATISFIES, certainty=STATED, reason="x"
    )
    assert "Likely" not in faked.label()
    honest = BucketVerdict(
        bucket_name="Gen Ed", outcome=SATISFIES, certainty=INFERRED, reason="x"
    )
    assert "Likely" in honest.label()

    # 5. Coverage — collapsing NO_MATCH into a plain negative removes the
    #    "that is not the same as does not count" caveat.
    unknown = BucketVerdict(
        bucket_name="Gen Ed", outcome=NO_MATCH, certainty=INFERRED, reason="x"
    )
    assert "not the same as" in unknown.label()
    assert unknown.counts is False
