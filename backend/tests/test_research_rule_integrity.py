"""Provenance guards on researched requirement rules.

Requirement rules are keyed on `(university, program)` **globally** — one row
serves every student in that cohort — while `university` and `program` are free
text each student sets on their own profile. That combination is the whole
attack: set your profile to a real cohort's exact strings, submit a page you
control, and `store_rules` deletes that cohort's verified rules and installs
yours. Nothing about the resulting rows looks wrong afterwards; the UI renders
them as "named in the requirement", and every other student in the program is
advised from an attacker's page.

Shape validation cannot see this — an attacker's page produces perfectly
well-formed rules — so the guard is on the *origin* of the pages actually
fetched. These tests exist because that guard has no other alarm: delete it and
every test in `test_requirement_rules.py` still passes, because they all use
York pages for a York program, which is exactly the case the guard permits.
"""
import pytest

from app.models.requirement_rule import BASIS_INFERRED, BASIS_STATED, RequirementRule
from app.research.program_rules import (
    ResearchFailed,
    check_requirements_url,
    expected_domain,
    store_rules,
)
from app.research.schema import ExtractedRule, RuleRejected

YORK = "York University"
CS = "Computer Science"

YORK_PAGE = [{"uri": "https://calendars.students.yorku.ca/x", "domain": "yorku.ca"}]
ATTACKER_PAGE = [{"uri": "https://attacker.tld/fake-calendar.html", "domain": "attacker.tld"}]


def _extracted(bucket="Non-Science General Education", **over) -> ExtractedRule:
    base = dict(
        bucket_name=bucket,
        credits_required=18.0,
        allowed_subjects=["AP/HUMA"],
        level_floor=None,
        level_ceiling=None,
        stated_codes=[],
        excluded_codes=[],
        excluded_subjects=[],
        source_quote="Students must complete 6.00 credits in AP/HUMA.",
        notes=None,
        basis=BASIS_STATED,
    )
    base.update(over)
    return ExtractedRule(**base)


async def _stored_rules(db, university=YORK, program=CS) -> list[RequirementRule]:
    from sqlalchemy import select

    result = await db.execute(
        select(RequirementRule).where(
            RequirementRule.university == university,
            RequirementRule.program == program,
        )
    )
    return list(result.scalars())


# ── Half (a): a known university's pages must be on its own domain ──


def test_a_known_universitys_page_must_be_on_its_own_domain():
    with pytest.raises(RuleRejected) as exc:
        check_requirements_url(YORK, "https://attacker.tld/fake-calendar.html")
    # The message has to name the domain that WOULD work, because the honest
    # case for this error is a student pasting the wrong link.
    assert "yorku.ca" in str(exc.value)


def test_the_universitys_own_page_is_accepted():
    url = "https://calendars.students.yorku.ca/2025-2026/faculty-rules"
    assert check_requirements_url(YORK, url) == url


def test_the_map_lookup_cannot_be_dodged_by_casing_or_spacing():
    """`"york  university"` must not read as an unknown school.

    An exact-match lookup would hand over the bypass: miss the map, take the
    unknown-university path, and skip the domain requirement entirely.
    """
    assert expected_domain("york  UNIVERSITY") == expected_domain(YORK) == "yorku.ca"

    with pytest.raises(RuleRejected):
        check_requirements_url("  york university  ", "https://attacker.tld/x")


def test_an_unknown_university_is_not_gated_by_the_map():
    """School 27 must still be researchable — refusing outright breaks growth."""
    assert expected_domain("Some New Polytechnic") is None
    url = "https://somenewpoly.example/requirements"
    assert check_requirements_url("Some New Polytechnic", url) == url


# ── Half (b): a run may not delete rules from a different origin ──


async def test_a_foreign_run_cannot_replace_a_cohorts_rules(db):
    """The attack, end to end: nothing written, nothing deleted."""
    await store_rules(db, YORK, CS, [_extracted()], YORK_PAGE, "groq/compound")
    before = await _stored_rules(db)
    assert len(before) == 1

    with pytest.raises(ResearchFailed):
        await store_rules(
            db,
            YORK,
            CS,
            [_extracted(bucket="Attacker Bucket", credits_required=0.0)],
            ATTACKER_PAGE,
            "groq/compound",
        )

    after = await _stored_rules(db)
    assert [r.bucket_name for r in after] == ["Non-Science General Education"]
    assert after[0].source_urls[0]["domain"] == "yorku.ca"


async def test_re_reading_the_same_source_still_replaces_rules(db):
    """The guard must not freeze a program: a calendar update has to land."""
    await store_rules(db, YORK, CS, [_extracted()], YORK_PAGE, "groq/compound")

    await store_rules(
        db,
        YORK,
        CS,
        [_extracted(credits_required=24.0)],
        YORK_PAGE,
        "groq/compound",
    )

    rules = await _stored_rules(db)
    assert len(rules) == 1
    assert float(rules[0].credits_required) == 24.0


async def test_first_writer_pins_the_domain_for_an_unknown_university(db):
    """An unknown school is open to the first researcher and closed after.

    Without this, the unknown-university path would be the bypass for the whole
    guard: claim a school the map has never heard of and overwrite at will.
    """
    university = "Some New Polytechnic"
    first = [{"uri": "https://somenewpoly.example/reqs", "domain": "somenewpoly.example"}]

    await store_rules(db, university, CS, [_extracted()], first, "groq/compound")

    with pytest.raises(ResearchFailed):
        await store_rules(
            db,
            university,
            CS,
            [_extracted(bucket="Attacker Bucket")],
            ATTACKER_PAGE,
            "groq/compound",
        )

    rules = await _stored_rules(db, university=university)
    assert [r.bucket_name for r in rules] == ["Non-Science General Education"]


async def test_an_unverifiable_origin_is_never_stored_as_stated(db):
    """`stated` renders in the UI as fact; only a verified page may claim it.

    A rule from a page we could not tie to the university is downgraded to
    `inferred` regardless of what the model asserted, because "the university's
    page states this" is precisely the claim that could not be checked.
    """
    university = "Some New Polytechnic"
    pages = [{"uri": "https://somenewpoly.example/reqs", "domain": "somenewpoly.example"}]

    await store_rules(
        db, university, CS, [_extracted(basis=BASIS_STATED)], pages, "groq/compound"
    )

    rules = await _stored_rules(db, university=university)
    assert rules[0].basis == BASIS_INFERRED


async def test_a_verified_page_keeps_its_stated_basis(db):
    """The downgrade must not flatten every rule — York's pages are verifiable."""
    await store_rules(
        db, YORK, CS, [_extracted(basis=BASIS_STATED)], YORK_PAGE, "groq/compound"
    )

    rules = await _stored_rules(db)
    assert rules[0].basis == BASIS_STATED
