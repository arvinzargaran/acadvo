"""Server-side eligibility / validation for AI-generated course picks.

The AI is grounded in the real catalog (see ``catalog.get_catalog``), but we never
trust the model's output blindly. These helpers let the recommendation and
semester-plan services:

  (a) confirm a returned code actually exists in the catalog (drop fabrications),
  (b) look up the authoritative name/credits to overwrite the LLM's text, and
  (c) decide whether a student is ELIGIBLE for a course given their completed
      courses (prerequisites) and their major GPA (GPA gates).

Prerequisite model (matches ``catalog``): ``prerequisites`` is a list of requirement
GROUPS. It is satisfied when, for EVERY group, at least ONE code in that group is in
the student's satisfied set (AND across groups, OR within a group). ``[]`` = none.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.degree import Course, CourseStatus
from app.services.degree import calculate_major_gpa
from app.services.document_parser import normalize_course_code


async def get_completed_codes(user_id: uuid.UUID, db: AsyncSession) -> set[str]:
    """Return the set of canonical codes the student has COMPLETED."""
    result = await db.execute(
        select(Course).where(
            Course.user_id == user_id,
            Course.status == CourseStatus.completed,
        )
    )
    return {
        normalize_course_code(c.course_code)
        for c in result.scalars()
        if c.course_code
    }


def missing_prerequisite_group(
    prerequisites: list[list[str]] | None,
    satisfied_codes: set[str],
) -> list[str] | None:
    """Return the FIRST requirement group that is not satisfied, or ``None`` if all
    groups are satisfied. ``satisfied_codes`` are canonical codes the student has
    completed (and, for plan-aware checks, scheduled earlier)."""
    for group in prerequisites or []:
        if not any(normalize_course_code(c) in satisfied_codes for c in group):
            return [normalize_course_code(c) for c in group]
    return None


def _fmt_gpa(value: float | None) -> str:
    return "N/A" if value is None else f"{round(value, 2)}"


def gate_blocked_reason(
    gpa_gate: dict | None,
    gpa_value: float | None,
    *,
    plan_phrasing: bool = False,
) -> str | None:
    """Return a human-readable reason string if ``gpa_value`` fails the gate, else
    ``None``. ``plan_phrasing`` softens the wording for a forward-looking plan
    ("unlocks once ...")."""
    if not gpa_gate:
        return None
    minimum = float(gpa_gate.get("min", 4.50))
    if gpa_value is not None and gpa_value >= minimum:
        return None
    scope = gpa_gate.get("scope", "")
    if plan_phrasing:
        return f"Unlocks once {scope} GPA ≥ {minimum:.2f} (currently {_fmt_gpa(gpa_value)})"
    return f"Requires {scope} GPA ≥ {minimum:.2f} (yours: {_fmt_gpa(gpa_value)})"


def evaluate_entry(
    entry: dict,
    satisfied_codes: set[str],
    gpa_by_scope: dict[str, float | None],
    *,
    plan_phrasing: bool = False,
) -> str | None:
    """Given a catalog ENTRY, the student's satisfied codes and a scope->gpa map,
    return a ``blocked_reason`` string if the student is INELIGIBLE, else ``None``.

    Prerequisites are checked first, then the GPA gate."""
    missing = missing_prerequisite_group(entry.get("prerequisites"), satisfied_codes)
    if missing:
        return f"Missing prerequisite {' or '.join(missing)}"
    gate = entry.get("gpa_gate")
    if gate:
        scope = gate.get("scope", "")
        gpa_value = gpa_by_scope.get(scope)
        reason = gate_blocked_reason(gate, gpa_value, plan_phrasing=plan_phrasing)
        if reason:
            return reason
    return None


async def gpa_by_scope_for_catalog(
    catalog: dict[str, dict],
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, float | None]:
    """Compute the student's major GPA for every distinct GPA-gate scope that
    appears in the catalog, returning ``{scope: gpa_value_or_None}``."""
    scopes = {
        e["gpa_gate"]["scope"]
        for e in catalog.values()
        if e.get("gpa_gate") and e["gpa_gate"].get("scope")
    }
    out: dict[str, float | None] = {}
    for scope in scopes:
        result = await calculate_major_gpa(user_id, db, faculty_prefix=scope)
        out[scope] = result["gpa"]
    return out


def format_prereqs(prerequisites: list[list[str]] | None) -> str:
    """Render a catalog ``prerequisites`` value for a prompt/context line."""
    if not prerequisites:
        return "none"
    groups = ["(" + " OR ".join(group) + ")" for group in prerequisites]
    return " AND ".join(groups)


def format_allowed_courses(
    catalog: dict[str, dict],
    exclude: set[str] | None = None,
) -> str:
    """Render the catalog as an ALLOWED-course list for grounding the LLM.

    Each line: ``- CODE | Name | X.X cr | prereqs: ... | gate: SCOPE GPA ≥ MIN``.
    Codes in ``exclude`` (already completed / in plan) are omitted."""
    exclude = exclude or set()
    lines = []
    for code in sorted(catalog):
        if code in exclude:
            continue
        entry = catalog[code]
        parts = [
            f"- {entry['course_code']}",
            entry["course_name"],
            f"{entry['credits']} cr",
            f"prereqs: {format_prereqs(entry.get('prerequisites'))}",
        ]
        gate = entry.get("gpa_gate")
        if gate:
            parts.append(f"gate: {gate.get('scope', '')} GPA ≥ {float(gate.get('min', 4.5)):.2f}")
        lines.append(" | ".join(parts))
    return "\n".join(lines) or "  (no catalog courses available)"
