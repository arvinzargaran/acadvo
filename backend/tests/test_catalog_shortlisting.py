"""Keeping a real catalog inside a prompt.

`format_allowed_courses` renders the ALLOWED COURSES block that grounds every
AI suggestion. It used to render the *whole* catalog, which was fine while a
catalog meant 22 hand-entered York courses and stopped being fine the moment one
was real: SFU's ingested 1,195 courses render to ~93k characters (~23k tokens),
over the per-request token cap. Growing the catalog — the entire point of the
ingestion pipeline — silently broke course search and the planner.

The shortlist is what fixes that, and these tests pin the three properties that
make it safe to narrow the list at all.
"""
from app.config import settings
from app.services.eligibility import (
    allowed_courses_budget_chars,
    format_allowed_courses,
    is_graduate_level,
    shortlist_for_query,
    shortlist_for_student,
    undergraduate_only,
)


def _catalog(*specs):
    """specs are (code, name) pairs."""
    return {
        code: {"course_code": code, "course_name": name, "credits": 3.0, "prerequisites": []}
        for code, name in specs
    }


def _big(subject, n, name="Some Course"):
    return _catalog(*[(f"{subject} {100 + i}", f"{name} {i}") for i in range(n)])


# ── Graduate filtering ───────────────────────────────────────────────


def test_graduate_numbering_is_recognised_per_convention():
    # Three-digit schools (SFU) put graduate work at 700+.
    assert not is_graduate_level("CMPT 225")
    assert not is_graduate_level("BISC 490")
    assert is_graduate_level("BISC 800")
    # 500-699 is graduate too — verified against the ingested SFU catalog, whose
    # 500-699 band is "Graduate Co-op", "Graduate Project", "Master of ...".
    assert is_graduate_level("CMPT 626")
    assert is_graduate_level("DMED 500")
    assert not is_graduate_level("BISC 499")
    # Four-digit schools (York) at 5000+.
    assert not is_graduate_level("LE/EECS 2030")
    assert is_graduate_level("LE/EECS 5101")


def test_graduate_courses_are_dropped_from_advising():
    """A real ingested catalog is the whole calendar, graduate courses included.

    The planner scheduled BISC 800 into a first-year term the first time an
    ingested catalog was large enough to contain one.
    """
    catalog = _catalog(("PSYC 100", "Intro"), ("PSYC 800", "Doctoral Seminar"))
    assert set(undergraduate_only(catalog)) == {"PSYC 100"}


def test_a_code_with_no_number_is_kept():
    assert undergraduate_only(_catalog(("ELECTIVE", "Open elective"))) == _catalog(
        ("ELECTIVE", "Open elective")
    )


# ── Query shortlisting ───────────────────────────────────────────────


def test_a_small_catalog_is_returned_whole():
    catalog = _big("CMPT", 10)
    assert shortlist_for_query(catalog, "anything") == catalog


def test_query_terms_rank_matching_courses_first():
    catalog = {**_big("BISC", 50, "Biology"), **_catalog(("PSYC 352", "Culture and Cognition"))}
    short = shortlist_for_query(catalog, "cognition", limit=5)
    assert "PSYC 352" in short


def test_a_subject_code_in_the_query_outweighs_one_title_word():
    catalog = {
        **_catalog(("PSYC 210", "Data Analysis")),
        **_big("BISC", 50, "Analysis of Living Systems"),
    }
    short = shortlist_for_query(catalog, "PSYC analysis", limit=3)
    assert "PSYC 210" in short


def test_excluded_courses_never_reach_the_prompt():
    catalog = _big("CMPT", 40)
    short = shortlist_for_query(catalog, "course", exclude={"CMPT 100"}, limit=5)
    assert "CMPT 100" not in short


# ── Student shortlisting ─────────────────────────────────────────────


def test_the_students_own_subjects_come_first():
    catalog = {**_big("BISC", 40), **_big("CMPT", 40)}
    short = shortlist_for_student(catalog, {"CMPT"}, limit=10)
    assert all(c.startswith("CMPT") for c in short)


def test_a_new_student_is_ranked_by_their_program_not_the_alphabet():
    """The bug this prevents produced a Psychology plan made of biology courses.

    A brand-new account has no courses, so there are no subjects to match. A
    plain alphabetical fallback put BISC and BPK at the top of the list handed to
    the planner, and the planner scheduled exactly that.
    """
    catalog = {**_big("BISC", 40, "Biology"), **_big("BPK", 40, "Kinesiology"), **_big("PSYC", 40, "Psychology")}
    short = shortlist_for_student(catalog, set(), program="Psychology", limit=10)
    assert all(c.startswith("PSYC") for c in short), sorted(short)[:5]


def test_courses_outside_the_program_remain_reachable():
    """Electives are part of a degree; the shortlist ranks, it does not exclude."""
    catalog = {**_big("PSYC", 5), **_big("BISC", 5)}
    short = shortlist_for_student(catalog, {"PSYC"}, program="Psychology", limit=10)
    assert any(c.startswith("BISC") for c in short)


# ── Rendering budget ─────────────────────────────────────────────────


def test_rendering_stops_at_the_character_budget():
    rendered = format_allowed_courses(_big("CMPT", 500), max_chars=500)
    assert len(rendered) <= 500


def test_ranked_input_is_rendered_in_rank_order():
    """Truncation must drop the least relevant candidate, not everything after M.

    Sorting inside the renderer would undo the shortlist's ranking and make the
    budget cut off exactly the courses the shortlist worked to surface.
    """
    ranked = {"ZZZZ 100": {"course_code": "ZZZZ 100", "course_name": "Best match", "credits": 3.0},
              "AAAA 100": {"course_code": "AAAA 100", "course_name": "Worse match", "credits": 3.0}}
    out = format_allowed_courses(ranked, ordered=True)
    assert out.index("ZZZZ 100") < out.index("AAAA 100")
    # Without `ordered`, the old alphabetical behaviour is preserved.
    out2 = format_allowed_courses(ranked)
    assert out2.index("AAAA 100") < out2.index("ZZZZ 100")


def test_budget_tracks_the_configured_request_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_MAX_REQUEST_TOKENS", 8000)
    assert allowed_courses_budget_chars() == int(8000 * 0.4) * 4
    # A caller whose own output is long asks for a smaller slice.
    assert allowed_courses_budget_chars(share=0.2) < allowed_courses_budget_chars()


def test_an_unbounded_account_still_gets_a_cap(monkeypatch):
    """'The catalog grew and every AI call started failing' is not a failure mode
    worth keeping, even where the provider would allow it."""
    monkeypatch.setattr(settings, "GROQ_MAX_REQUEST_TOKENS", 0)
    assert allowed_courses_budget_chars() == 48000


def test_the_elective_tail_is_spread_across_subjects():
    """One subject must not monopolise the part of the list that gets truncated.

    The tail is where electives come from. Sorted order starts at the
    alphabetical beginning of the catalog and stops wherever the budget runs
    out, which on the full SFU catalog gave a French major a plan whose every
    elective was BISC — not because biology suited them, but because "B" is
    early and the list was cut off before the rest of the alphabet.
    """
    catalog = {}
    for subject in ("BISC", "BPK", "CHEM", "HIST", "PHIL"):
        catalog.update(_big(subject, 30))
    short = shortlist_for_student(catalog, set(), program="French", limit=25)
    subjects = {c.split()[0] for c in short}
    assert len(subjects) >= 4, sorted(short)


def test_the_students_own_subject_still_wins_the_top_of_the_list():
    """Spreading the tail must not dilute the part that matters."""
    catalog = {**_big("FREN", 30, "French"), **_big("BISC", 30, "Biology")}
    short = shortlist_for_student(catalog, set(), program="French", limit=30)
    assert all(c.startswith("FREN") for c in list(short)[:30])
