"""Per-university program rules that must not be hardcoded into general code.

This holds *major/subject GPA gates* and *course-numbering rules*. It started as
just the GPA gates — the subset-GPA thresholds some
programs use to gate upper-year courses (e.g. York gates 2000+ EECS courses
behind a 4.50 EECS-major GPA). Keyed by canonical university name, which must
match ``User.university`` and the keys in ``grading_scales.py``.

Universities absent from this map simply have no major-GPA gate, so the app
shows and asserts none — instead of applying York's EECS gate to everyone.
"""

# Each gate:
#   scope   — subject/faculty prefix that defines the "major" course subset
#             (matched case-insensitively against course codes)
#   min     — minimum subset GPA required, on that university's grading scale
#   governs — human description of the courses the gate governs (for prompts)
MAJOR_GPA_GATES: dict[str, list[dict]] = {
    "York University": [
        {"scope": "EECS", "min": 4.50, "governs": "2000/3000/4000-level EECS courses"},
    ],
}


def get_major_gpa_gates(university: str | None) -> list[dict]:
    """Return the list of major-GPA gate definitions for ``university`` (empty
    when the university defines none)."""
    if not university:
        return []
    return MAJOR_GPA_GATES.get(university, [])


# ── Course numbering: which numbers mean "graduate" ──────────────────
#
# There is no shared convention, and the collision is not academic. The general
# heuristic in ``eligibility.is_graduate_level`` reads a four-digit number as
# York-style and calls it graduate only at 5000+. UofT numbers its GRADUATE
# courses with four digits (``CSC2515``) and its undergraduate ones with three
# (``CSC148``) — so under the general rule every UofT graduate course reads as
# undergraduate, and the planner is free to put a PhD-level course in a first
# year student's Fall term.
#
# Each rule may set either or both of:
#   min_number         — this number and above is graduate
#   graduate_digits    — a catalog number with this many digits is graduate
GRADUATE_RULES: dict[str, dict] = {
    # Four-digit school: 1000-4000 undergraduate, 5000+ graduate.
    "York University": {"min_number": 5000},
    # Three-digit undergraduate (CSC 148); four-digit is graduate (CSC 2515).
    "University of Toronto": {"graduate_digits": 4},
    # Three-digit undergraduate (CPS 209); four-digit is graduate (CP 8201).
    "Toronto Metropolitan University": {"graduate_digits": 4},
    # 100-400 undergraduate; 500+ is graduate-level (senior undergrads need
    # permission, so excluding them is the conservative direction).
    "University of Waterloo": {"min_number": 500},
    "Simon Fraser University": {"min_number": 500},
    # 100-499 undergraduate, 500+ graduate. The general heuristic already lands
    # here for three-digit codes; stated explicitly so a future change to that
    # fallback cannot silently move UBC with it.
    "University of British Columbia": {"min_number": 500},
}


def get_graduate_rule(university: str | None) -> dict | None:
    """Return the graduate-numbering rule for ``university``, or None when the
    school has no entry (the caller then falls back to the general heuristic)."""
    if not university:
        return None
    return GRADUATE_RULES.get(university)
