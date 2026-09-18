"""York University BSc Honours Computer Science course catalog seed data.

Ground truth transcribed from the 2025-2026 Degree Checklist. Each entry is the
canonical catalog record for a course: canonical (faculty-prefixed) code, name,
credits, subject faculty, prerequisites and GPA gate.

``prerequisites`` uses the requirement-group shape shared with
``CatalogCourse.prerequisites``: a list of groups, each a list of alternative
canonical codes. ALL groups must be satisfied (AND); any one code in a group
satisfies it (OR). ``[]`` means no prerequisites.

``gpa_gate`` is ``{"scope": "EECS", "min": 4.50}`` for the ~2000/3000/4000-level
EECS courses that carry the 4.50 EECS-GPA gate, else ``None``.
"""
from sqlalchemy.ext.asyncio import AsyncSession

YORK_UNIVERSITY = "York University"

_EECS_GATE = {"scope": "EECS", "min": 4.50}

# Each tuple: (code, name, credits, subject_faculty, prerequisites, gpa_gate)
YORK_CS_COURSES: list[dict] = [
    # ── First year ───────────────────────────────────────────────────
    {"course_code": "LE/EECS 1001", "course_name": "Research Directions in Computing",
     "credits": 1.0, "subject_faculty": "EECS", "prerequisites": [], "gpa_gate": None},
    {"course_code": "LE/EECS 1012", "course_name": "Introduction to Computing: A Net-centric Approach",
     "credits": 3.0, "subject_faculty": "EECS", "prerequisites": [], "gpa_gate": None},
    {"course_code": "LE/EECS 1015", "course_name": "Introduction to Computer Science and Programming",
     "credits": 3.0, "subject_faculty": "EECS", "prerequisites": [], "gpa_gate": None},
    {"course_code": "LE/EECS 1019", "course_name": "Discrete Mathematics for Computer Science",
     "credits": 3.0, "subject_faculty": "EECS", "prerequisites": [], "gpa_gate": None},
    {"course_code": "LE/EECS 1022", "course_name": "Introduction to Object Oriented Programming",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 1012", "LE/EECS 1015"]], "gpa_gate": None},
    {"course_code": "SC/MATH 1300", "course_name": "Differential Calculus with Applications",
     "credits": 3.0, "subject_faculty": "MATH", "prerequisites": [], "gpa_gate": None},
    {"course_code": "SC/MATH 1310", "course_name": "Integral Calculus with Applications",
     "credits": 3.0, "subject_faculty": "MATH",
     "prerequisites": [["SC/MATH 1300"]], "gpa_gate": None},

    # ── Second year ──────────────────────────────────────────────────
    {"course_code": "LE/EECS 2001", "course_name": "Introduction to the Theory of Computation",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 1022"], ["LE/EECS 1019"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 2021", "course_name": "Computer Organization",
     "credits": 4.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 1022"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 2030", "course_name": "Advanced Object Oriented Programming",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 1022"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 2031", "course_name": "Software Tools",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 1022"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 2101", "course_name": "Fundamentals of Data Structures",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 1019"], ["LE/EECS 2030"]], "gpa_gate": _EECS_GATE},
    {"course_code": "SC/MATH 1090", "course_name": "Introduction to Logic for Computer Science",
     "credits": 3.0, "subject_faculty": "MATH",
     "prerequisites": [["LE/EECS 1019"]], "gpa_gate": None},
    {"course_code": "SC/MATH 2030", "course_name": "Elementary Probability",
     "credits": 3.0, "subject_faculty": "MATH",
     "prerequisites": [["SC/MATH 1310"]], "gpa_gate": None},

    # ── Third year ───────────────────────────────────────────────────
    {"course_code": "LE/EECS 3000", "course_name": "Professional Practice in Computing",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 2030"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 3101", "course_name": "Design and Analysis of Algorithms",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["SC/MATH 1310"], ["SC/MATH 1090"], ["LE/EECS 2101"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 3311", "course_name": "Software Design",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["SC/MATH 1090"], ["LE/EECS 2030"], ["LE/EECS 2031"], ["LE/EECS 2101"]],
     "gpa_gate": _EECS_GATE},
    # NOTE: the 2025-2026 checklist lists these five courses' prerequisites only as
    # "other specified courses" without naming them, so we do NOT invent an exact
    # prereq list. We use a single CONSERVATIVE gateway prerequisite — Fundamentals
    # of Data Structures (LE/EECS 2101) — which every 3000-level EECS course sits
    # behind. This is a documented lower bound: enough to keep semester-plan ordering
    # sane (they land after the 2000-level core) without over-claiming specifics.
    {"course_code": "LE/EECS 3215", "course_name": "Embedded Systems",
     "credits": 4.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 2101"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 3221", "course_name": "Operating System Fundamentals",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 2101"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 3401", "course_name": "Introduction to Artificial Intelligence and Logic Programming",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 2101"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 3421", "course_name": "Introduction to Database Systems",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 2101"]], "gpa_gate": _EECS_GATE},
    {"course_code": "LE/EECS 3461", "course_name": "User Interfaces",
     "credits": 3.0, "subject_faculty": "EECS",
     "prerequisites": [["LE/EECS 2101"]], "gpa_gate": _EECS_GATE},
]

# Mutually-exclusive equivalent courses: completing ANY one member satisfies the
# whole group, so the others must never be recommended/planned as if still needed.
# From the checklist's first-year "A or B" alternatives.
EQUIVALENT_GROUPS: list[set[str]] = [
    {"LE/EECS 1012", "LE/EECS 1015"},  # net-centric intro  OR  CS-and-programming intro
]


# Provenance shown to students via ``get_catalog_status``. Distinguishable from
# an API ingest (``sfu_course_outlines``) and from a checklist promotion
# (``checklist:<label>``), so a later authoritative York import is visibly a
# different, better source than this hand transcription.
SOURCE = "manual:york-bsc-hons-cs-2025-2026"


async def seed_catalog(db: AsyncSession, university: str = YORK_UNIVERSITY) -> int:
    """Idempotently upsert the York CS catalog rows. Returns the number written.

    Delegates to the shared ``upsert_catalog`` rather than carrying its own
    PostgreSQL-only ``ON CONFLICT``: that made this the one write path the SQLite
    test harness could not exercise, which is part of why it went unnoticed that
    **nothing ever called it**. The 22 courses transcribed here existed only in
    source; a fresh deployment had an empty catalog and every York student was
    silently advised off their own upload.
    """
    from app.ingest.store import upsert_catalog

    rows = [
        {
            "course_code": c["course_code"],
            "course_name": c["course_name"],
            "credits": c["credits"],
            "subject_faculty": c.get("subject_faculty"),
            "prerequisites": c.get("prerequisites") or [],
            "gpa_gate": c.get("gpa_gate"),
        }
        for c in YORK_CS_COURSES
    ]
    return await upsert_catalog(db, university, rows, source=SOURCE)
