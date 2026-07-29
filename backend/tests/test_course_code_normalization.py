"""Unit tests for generalized course-code normalization.

Covers BOTH York-style codes (faculty-prefix restoration) and generic
``SUBJECT NUMBER`` codes (e.g. SFU's 3-digit numbers with an optional trailing
letter), plus the guard against treating 1-2 digit numbers as course codes.
"""
from app.services.document_parser import (
    extract_course_codes,
    normalize_course_code,
    subject_of,
)


# ── York-style: faculty-prefix restoration (must not regress) ─────────

def test_york_restores_eecs_faculty_from_bare_subject():
    assert normalize_course_code("EECS2101") == "LE/EECS 2101"


def test_york_restores_math_faculty():
    assert normalize_course_code("MATH 1300") == "SC/MATH 1300"


def test_york_keeps_given_prefix_and_drops_credit_suffix():
    assert normalize_course_code("le/eecs 2101 3.00") == "LE/EECS 2101"


def test_york_science_prefix_and_credit_suffix():
    assert normalize_course_code("SC/BIOL 1000 3.00") == "SC/BIOL 1000"


# ── SFU / generic bare SUBJECT NUMBER form ───────────────────────────

def test_generic_lowercase_gets_uppercased():
    assert normalize_course_code("cmpt 225") == "CMPT 225"


def test_generic_missing_space_gets_spaced():
    assert normalize_course_code("CMPT225") == "CMPT 225"


def test_generic_trailing_letter_uppercased():
    assert normalize_course_code("CMPT 105w") == "CMPT 105W"


def test_generic_canonical_form_is_identity():
    # CRITICAL: the SFU catalog stores exactly this form; it must not change.
    assert normalize_course_code("CMPT 225") == "CMPT 225"


def test_generic_unknown_subject_gets_no_faculty_prefix():
    assert normalize_course_code("MACM 101") == "MACM 101"


# ── subject_of for both formats ──────────────────────────────────────

def test_subject_of_generic():
    assert subject_of("CMPT 225") == "CMPT"


def test_subject_of_generic_with_trailing_letter():
    assert subject_of("CMPT 105W") == "CMPT"


def test_subject_of_york():
    assert subject_of("LE/EECS 2101") == "EECS"


def test_subject_of_lowercase_input():
    assert subject_of("cmpt 225") == "CMPT"


# ── 1-2 digit numbers are NOT course codes ───────────────────────────

def test_one_or_two_digit_numbers_are_not_codes():
    assert extract_course_codes("Complete 60 units, MATH 12 does not count.") == []


def test_two_digit_number_not_normalized_as_code():
    # No valid 3-4 digit code present -> input returned trimmed, unchanged.
    assert normalize_course_code("CMPT 42") == "CMPT 42"


# ── extract_course_codes works for both formats ──────────────────────

def test_extract_mixed_formats():
    text = "Prereq: CMPT 225 or MACM 101; also LE/EECS 2101 and cmpt 105w."
    assert extract_course_codes(text) == [
        "CMPT 225",
        "MACM 101",
        "LE/EECS 2101",
        "CMPT 105W",
    ]
