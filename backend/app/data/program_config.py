"""Per-university program rules that must not be hardcoded into general code.

Today this holds *major/subject GPA gates* — the subset-GPA thresholds some
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
