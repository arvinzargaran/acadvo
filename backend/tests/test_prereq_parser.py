"""Unit tests for the natural-language prerequisite parser (real SFU strings).

Verifies AND-of-OR-groups (CNF) semantics and that prose with no course codes
yields no machine-checkable prerequisite (never a fabricated code)."""
from app.ingest.prereq_parser import parse_prerequisites


def _as_sets(groups):
    return {frozenset(g) for g in groups}


def test_single_prerequisite():
    assert parse_prerequisites("MACM 101.") == [["MACM 101"]]


def test_and_two_required():
    assert _as_sets(parse_prerequisites("CMPT 225 and MACM 201, with a minimum grade of C-.")) == {
        frozenset({"CMPT 225"}),
        frozenset({"MACM 201"}),
    }


def test_or_alternatives_one_group():
    assert parse_prerequisites("CMPT 120 or CMPT 130, both with a grade of at least C.") == [
        ["CMPT 120", "CMPT 130"]
    ]


def test_comma_is_or():
    # "CMPT 125, CMPT 129 or CMPT 135" -> a single OR-group of three.
    assert _as_sets(parse_prerequisites("CMPT 125, CMPT 129 or CMPT 135.")) == {
        frozenset({"CMPT 125", "CMPT 129", "CMPT 135"})
    }


def test_nested_boolean_to_cnf():
    got = parse_prerequisites(
        "(MACM 101 and (CMPT 125, CMPT 129 or CMPT 135)) or (ENSC 251 and ENSC 252), "
        "all with a minimum grade of C-."
    )
    # (M and (A)) or (E1 and E2), A = {C125,C129,C135}
    #   -> {M,E1} AND {M,E2} AND {A,E1} AND {A,E2}
    assert _as_sets(got) == {
        frozenset({"MACM 101", "ENSC 251"}),
        frozenset({"MACM 101", "ENSC 252"}),
        frozenset({"CMPT 125", "CMPT 129", "CMPT 135", "ENSC 251"}),
        frozenset({"CMPT 125", "CMPT 129", "CMPT 135", "ENSC 252"}),
    }


def test_no_codes_returns_empty():
    assert parse_prerequisites("Permission of the department.") == []
    assert parse_prerequisites("60 units.") == []
    assert parse_prerequisites("") == []
    assert parse_prerequisites(None) == []


def test_never_invents_codes():
    # Every code in the output must appear in the source text.
    text = "CMPT 225 and MACM 201."
    for group in parse_prerequisites(text):
        for code in group:
            assert code.replace(" ", "") in text.replace(" ", "")
