"""Per-university credit models — how much one course is *worth*.

The engine used to assume York's model everywhere: a standard course is 3.0
credits, a full-time term is 12-15 credits, a degree is 120. At Waterloo a
course is 0.5 units and an honours degree is ~20.0; at UofT a half-course is
0.5 credits and a four-year degree is 20.0. Under York's numbers a Waterloo
plan chases 120 units — six degrees' worth — and every elective placeholder is
six courses in a trench coat.

The deliberate design choice here is that **almost nothing is hardcoded**. A
table of per-school degree totals would be invented data of exactly the kind
``ingest/SOURCES.md`` forbids, and it would be wrong for every student whose
program differs from the "typical" one. Instead the model is *derived*, in
descending order of authority:

1. The student's own parsed checklist — ``total_credits_required`` and the
   ``credit_value`` on their own course rows. This is their real program, from
   the official document they uploaded.
2. The seeded ``CatalogCourse`` rows for their university — the modal course
   credit across a real, ingested catalog.
3. ``COURSE_UNITS`` below: the credit value of one standard one-term course,
   for the handful of schools where that figure is structural and certain.
4. A neutral 3.0 fallback, flagged as such.

Only step 3 is a constant, and it holds a single number per school that does
not vary by program. Degree totals are never hardcoded: when the checklist
does not supply one, the estimate is *structural* (a four-year, five-courses-a-
term degree is 40 courses) and every message built from it says "about".
"""
from __future__ import annotations

from dataclasses import dataclass

# Credits/units carried by ONE standard one-term course. Program-independent
# and published by each registrar; that is why these are safe as constants when
# a degree total would not be. A school absent here is not a gap — its model is
# inferred from the student's own courses, which is strictly better data.
COURSE_UNITS: dict[str, float] = {
    "York University": 3.0,          # "3.00 credits" per one-term course
    "Simon Fraser University": 3.0,  # 3 units
    "University of Toronto": 0.5,    # half-course (H); a Y course is 1.0
    "University of Waterloo": 0.5,   # 0.5 units
}

# What each school calls the thing. Cosmetic, but "120 credits" vs "20.0 units"
# is the difference between advice a student recognises and advice they don't.
UNIT_LABELS: dict[str, str] = {
    "University of Waterloo": "units",
    "Simon Fraser University": "units",
}

# A full-time term is five courses just about everywhere; the credit figure is
# that count times the school's unit, never a separate constant.
COURSES_PER_FULL_TERM = 5
# Eight terms of five courses. Used ONLY when the student's checklist carries no
# total of its own, and always reported as an approximation.
COURSES_PER_DEGREE = 40

FALLBACK_UNIT = 3.0


@dataclass(frozen=True)
class CreditModel:
    """How to count credits for one student at one university."""

    unit: float           # credits carried by one standard one-term course
    label: str            # "credits" or "units"
    degree_total: float   # credits for the whole degree
    total_is_estimate: bool   # True when derived rather than read off a checklist
    unit_is_fallback: bool    # True when `unit` is the neutral default

    @property
    def full_term(self) -> float:
        """Credits in a normal full-time term."""
        return round(self.unit * COURSES_PER_FULL_TERM, 2)

    def courses_for(self, credits: float) -> int:
        """How many standard courses ``credits`` worth of gap represents."""
        return int(credits // self.unit) if self.unit > 0 else 0

    def fmt(self, credits: float) -> str:
        """Format a credit amount the way this university writes it."""
        text = f"{credits:g}" if self.unit >= 1 else f"{credits:.1f}"
        return f"{text} {self.label}"


def _modal_unit(values) -> float | None:
    """The most common positive credit value in ``values``, or None.

    Modal rather than mean on purpose: a transcript mixes 3.0-credit courses
    with the odd 1.0-credit seminar and 6.0-credit full-year course, and the
    mean of that is a number no course actually carries.
    """
    counts: dict[float, int] = {}
    for v in values:
        try:
            f = round(float(v), 2)
        except (TypeError, ValueError):
            continue
        if f > 0:
            counts[f] = counts.get(f, 0) + 1
    if not counts:
        return None
    # Ties break toward the larger unit: a half-empty transcript is more likely
    # to under-count the standard course than to invent a bigger one.
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def get_credit_model(
    university: str | None,
    *,
    student_credit_values=(),
    catalog_credit_values=(),
    total_credits_required: float | None = None,
) -> CreditModel:
    """Build the credit model for one student.

    ``student_credit_values`` are the ``credit_value``s on the student's own
    course rows, ``catalog_credit_values`` those of the seeded catalog for their
    university, and ``total_credits_required`` the total their checklist stated
    (None when they have no checklist, or it carried no total).
    """
    unit = _modal_unit(student_credit_values)
    if unit is None:
        unit = _modal_unit(catalog_credit_values)
    unit_is_fallback = False
    if unit is None:
        unit = COURSE_UNITS.get(university or "")
    if unit is None:
        unit = FALLBACK_UNIT
        unit_is_fallback = True

    # A published unit for a known school beats one inferred from a handful of
    # rows: a UofT student who has typed only two full-year (1.0) courses would
    # otherwise get a 1.0 unit and a 40-credit degree.
    published = COURSE_UNITS.get(university or "")
    if published is not None and unit != published:
        inferred_from = list(student_credit_values) or list(catalog_credit_values)
        if len(inferred_from) < COURSES_PER_FULL_TERM:
            unit = published

    total = float(total_credits_required) if total_credits_required else 0.0
    total_is_estimate = total <= 0
    if total_is_estimate:
        total = unit * COURSES_PER_DEGREE

    label = UNIT_LABELS.get(university or "", "credits")
    return CreditModel(
        unit=unit,
        label=label,
        degree_total=total,
        total_is_estimate=total_is_estimate,
        unit_is_fallback=unit_is_fallback,
    )
