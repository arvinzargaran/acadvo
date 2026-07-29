"""
University-specific grading scales for Canadian universities.

Each scale maps letter grades to GPA points following the official scale
published by that university. Keys must match the university name stored
in the User model (which mirrors the frontend CANADIAN_UNIVERSITIES list).
"""

FALLBACK_SCALE = {
    "scale_type": "4.0",
    "max_points": 4.0,
    "grades": [
        {"letter": "A+", "points": 4.0, "min_percent": 90},
        {"letter": "A",  "points": 4.0, "min_percent": 85},
        {"letter": "A-", "points": 3.7, "min_percent": 80},
        {"letter": "B+", "points": 3.3, "min_percent": 77},
        {"letter": "B",  "points": 3.0, "min_percent": 73},
        {"letter": "B-", "points": 2.7, "min_percent": 70},
        {"letter": "C+", "points": 2.3, "min_percent": 67},
        {"letter": "C",  "points": 2.0, "min_percent": 63},
        {"letter": "C-", "points": 1.7, "min_percent": 60},
        {"letter": "D+", "points": 1.3, "min_percent": 57},
        {"letter": "D",  "points": 1.0, "min_percent": 53},
        {"letter": "D-", "points": 0.7, "min_percent": 50},
        {"letter": "F",  "points": 0.0, "min_percent": 0},
    ],
}


GRADING_SCALES: dict[str, dict] = {

    # ── York University — 9-point scale ──────────────────────────────
    "York University": {
        "scale_type": "9.0",
        "max_points": 9.0,
        "grades": [
            {"letter": "A+", "points": 9.0, "min_percent": 90},
            {"letter": "A",  "points": 8.0, "min_percent": 80},
            {"letter": "B+", "points": 7.0, "min_percent": 75},
            {"letter": "B",  "points": 6.0, "min_percent": 70},
            {"letter": "C+", "points": 5.0, "min_percent": 65},
            {"letter": "C",  "points": 4.0, "min_percent": 60},
            {"letter": "D+", "points": 3.0, "min_percent": 55},
            {"letter": "D",  "points": 2.0, "min_percent": 50},
            {"letter": "E",  "points": 1.0, "min_percent": 40},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── University of Toronto — 4.0 scale ────────────────────────────
    "University of Toronto": {
        "scale_type": "4.0",
        "max_points": 4.0,
        "grades": [
            {"letter": "A+", "points": 4.0, "min_percent": 90},
            {"letter": "A",  "points": 4.0, "min_percent": 85},
            {"letter": "A-", "points": 3.7, "min_percent": 80},
            {"letter": "B+", "points": 3.3, "min_percent": 77},
            {"letter": "B",  "points": 3.0, "min_percent": 73},
            {"letter": "B-", "points": 2.7, "min_percent": 70},
            {"letter": "C+", "points": 2.3, "min_percent": 67},
            {"letter": "C",  "points": 2.0, "min_percent": 63},
            {"letter": "C-", "points": 1.7, "min_percent": 60},
            {"letter": "D+", "points": 1.3, "min_percent": 57},
            {"letter": "D",  "points": 1.0, "min_percent": 53},
            {"letter": "D-", "points": 0.7, "min_percent": 50},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── Toronto Metropolitan University (Ryerson) — 4.33 scale ───────
    "Toronto Metropolitan University": {
        "scale_type": "4.33",
        "max_points": 4.33,
        "grades": [
            {"letter": "A+", "points": 4.33, "min_percent": 90},
            {"letter": "A",  "points": 4.00, "min_percent": 85},
            {"letter": "A-", "points": 3.67, "min_percent": 80},
            {"letter": "B+", "points": 3.33, "min_percent": 77},
            {"letter": "B",  "points": 3.00, "min_percent": 73},
            {"letter": "B-", "points": 2.67, "min_percent": 70},
            {"letter": "C+", "points": 2.33, "min_percent": 67},
            {"letter": "C",  "points": 2.00, "min_percent": 63},
            {"letter": "C-", "points": 1.67, "min_percent": 60},
            {"letter": "D+", "points": 1.33, "min_percent": 57},
            {"letter": "D",  "points": 1.00, "min_percent": 53},
            {"letter": "D-", "points": 0.67, "min_percent": 50},
            {"letter": "F",  "points": 0.00, "min_percent": 0},
        ],
    },

    # ── University of Waterloo — 4.0 scale (percentage-based with letter mapping)
    "University of Waterloo": {
        "scale_type": "4.0",
        "max_points": 4.0,
        "grades": [
            {"letter": "A+", "points": 4.0, "min_percent": 90},
            {"letter": "A",  "points": 4.0, "min_percent": 85},
            {"letter": "A-", "points": 3.7, "min_percent": 80},
            {"letter": "B+", "points": 3.3, "min_percent": 77},
            {"letter": "B",  "points": 3.0, "min_percent": 73},
            {"letter": "B-", "points": 2.7, "min_percent": 70},
            {"letter": "C+", "points": 2.3, "min_percent": 67},
            {"letter": "C",  "points": 2.0, "min_percent": 63},
            {"letter": "C-", "points": 1.7, "min_percent": 60},
            {"letter": "D+", "points": 1.3, "min_percent": 57},
            {"letter": "D",  "points": 1.0, "min_percent": 53},
            {"letter": "D-", "points": 0.7, "min_percent": 50},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── Western University — 4.0 scale (King's/Brescia/Huron same scale)
    "Western University": {
        "scale_type": "4.0",
        "max_points": 4.0,
        "grades": [
            {"letter": "A+", "points": 4.0, "min_percent": 90},
            {"letter": "A",  "points": 4.0, "min_percent": 80},
            {"letter": "B",  "points": 3.0, "min_percent": 70},
            {"letter": "C",  "points": 2.0, "min_percent": 60},
            {"letter": "D",  "points": 1.0, "min_percent": 50},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── Queen's University — 4.3 scale ───────────────────────────────
    "Queen's University": {
        "scale_type": "4.3",
        "max_points": 4.3,
        "grades": [
            {"letter": "A+", "points": 4.3, "min_percent": 90},
            {"letter": "A",  "points": 4.0, "min_percent": 85},
            {"letter": "A-", "points": 3.7, "min_percent": 80},
            {"letter": "B+", "points": 3.3, "min_percent": 77},
            {"letter": "B",  "points": 3.0, "min_percent": 73},
            {"letter": "B-", "points": 2.7, "min_percent": 70},
            {"letter": "C+", "points": 2.3, "min_percent": 67},
            {"letter": "C",  "points": 2.0, "min_percent": 63},
            {"letter": "C-", "points": 1.7, "min_percent": 60},
            {"letter": "D+", "points": 1.3, "min_percent": 57},
            {"letter": "D",  "points": 1.0, "min_percent": 53},
            {"letter": "D-", "points": 0.7, "min_percent": 50},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── McMaster University — 12-point scale ─────────────────────────
    "McMaster University": {
        "scale_type": "12.0",
        "max_points": 12.0,
        "grades": [
            {"letter": "A+", "points": 12.0, "min_percent": 90},
            {"letter": "A",  "points": 11.0, "min_percent": 85},
            {"letter": "A-", "points": 10.0, "min_percent": 80},
            {"letter": "B+", "points": 9.0,  "min_percent": 77},
            {"letter": "B",  "points": 8.0,  "min_percent": 73},
            {"letter": "B-", "points": 7.0,  "min_percent": 70},
            {"letter": "C+", "points": 6.0,  "min_percent": 67},
            {"letter": "C",  "points": 5.0,  "min_percent": 63},
            {"letter": "C-", "points": 4.0,  "min_percent": 60},
            {"letter": "D+", "points": 3.0,  "min_percent": 57},
            {"letter": "D",  "points": 2.0,  "min_percent": 53},
            {"letter": "D-", "points": 1.0,  "min_percent": 50},
            {"letter": "F",  "points": 0.0,  "min_percent": 0},
        ],
    },

    # ── University of Ottawa — 10-point scale ────────────────────────
    "University of Ottawa": {
        "scale_type": "10.0",
        "max_points": 10.0,
        "grades": [
            {"letter": "A+", "points": 10.0, "min_percent": 90},
            {"letter": "A",  "points": 9.0,  "min_percent": 85},
            {"letter": "A-", "points": 8.0,  "min_percent": 80},
            {"letter": "B+", "points": 7.0,  "min_percent": 75},
            {"letter": "B",  "points": 6.0,  "min_percent": 70},
            {"letter": "C+", "points": 5.0,  "min_percent": 65},
            {"letter": "C",  "points": 4.0,  "min_percent": 60},
            {"letter": "D+", "points": 3.0,  "min_percent": 55},
            {"letter": "D",  "points": 2.0,  "min_percent": 50},
            {"letter": "E",  "points": 1.0,  "min_percent": 40},
            {"letter": "F",  "points": 0.0,  "min_percent": 0},
        ],
    },

    # ── Carleton University — 12-point scale ─────────────────────────
    "Carleton University": {
        "scale_type": "12.0",
        "max_points": 12.0,
        "grades": [
            {"letter": "A+", "points": 12.0, "min_percent": 90},
            {"letter": "A",  "points": 11.0, "min_percent": 85},
            {"letter": "A-", "points": 10.0, "min_percent": 80},
            {"letter": "B+", "points": 9.0,  "min_percent": 77},
            {"letter": "B",  "points": 8.0,  "min_percent": 73},
            {"letter": "B-", "points": 7.0,  "min_percent": 70},
            {"letter": "C+", "points": 6.0,  "min_percent": 67},
            {"letter": "C",  "points": 5.0,  "min_percent": 63},
            {"letter": "C-", "points": 4.0,  "min_percent": 60},
            {"letter": "D+", "points": 3.0,  "min_percent": 57},
            {"letter": "D",  "points": 2.0,  "min_percent": 53},
            {"letter": "D-", "points": 1.0,  "min_percent": 50},
            {"letter": "F",  "points": 0.0,  "min_percent": 0},
        ],
    },

    # ── McGill University — 4.0 scale ────────────────────────────────
    "McGill University": {
        "scale_type": "4.0",
        "max_points": 4.0,
        "grades": [
            {"letter": "A",  "points": 4.0, "min_percent": 85},
            {"letter": "A-", "points": 3.7, "min_percent": 80},
            {"letter": "B+", "points": 3.3, "min_percent": 75},
            {"letter": "B",  "points": 3.0, "min_percent": 70},
            {"letter": "B-", "points": 2.7, "min_percent": 65},
            {"letter": "C+", "points": 2.3, "min_percent": 60},
            {"letter": "C",  "points": 2.0, "min_percent": 55},
            {"letter": "D",  "points": 1.0, "min_percent": 50},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── Concordia University — 4.3 scale ─────────────────────────────
    "Concordia University": {
        "scale_type": "4.3",
        "max_points": 4.3,
        "grades": [
            {"letter": "A+", "points": 4.3, "min_percent": 90},
            {"letter": "A",  "points": 4.0, "min_percent": 85},
            {"letter": "A-", "points": 3.7, "min_percent": 80},
            {"letter": "B+", "points": 3.3, "min_percent": 77},
            {"letter": "B",  "points": 3.0, "min_percent": 73},
            {"letter": "B-", "points": 2.7, "min_percent": 70},
            {"letter": "C+", "points": 2.3, "min_percent": 67},
            {"letter": "C",  "points": 2.0, "min_percent": 63},
            {"letter": "C-", "points": 1.7, "min_percent": 60},
            {"letter": "D+", "points": 1.3, "min_percent": 57},
            {"letter": "D",  "points": 1.0, "min_percent": 53},
            {"letter": "D-", "points": 0.7, "min_percent": 50},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── Simon Fraser University — 4.33 scale ─────────────────────────
    "Simon Fraser University": {
        "scale_type": "4.33",
        "max_points": 4.33,
        "grades": [
            {"letter": "A+", "points": 4.33, "min_percent": 95},
            {"letter": "A",  "points": 4.00, "min_percent": 90},
            {"letter": "A-", "points": 3.67, "min_percent": 85},
            {"letter": "B+", "points": 3.33, "min_percent": 80},
            {"letter": "B",  "points": 3.00, "min_percent": 75},
            {"letter": "B-", "points": 2.67, "min_percent": 70},
            {"letter": "C+", "points": 2.33, "min_percent": 65},
            {"letter": "C",  "points": 2.00, "min_percent": 60},
            {"letter": "C-", "points": 1.67, "min_percent": 55},
            {"letter": "D",  "points": 1.00, "min_percent": 50},
            {"letter": "F",  "points": 0.00, "min_percent": 0},
        ],
    },

    # ── University of British Columbia — percentage-based ─────────────
    "University of British Columbia": {
        "scale_type": "percentage",
        "max_points": 100.0,
        "grades": [
            {"letter": "A+", "points": 95.0, "min_percent": 90},
            {"letter": "A",  "points": 87.5, "min_percent": 85},
            {"letter": "A-", "points": 82.5, "min_percent": 80},
            {"letter": "B+", "points": 78.5, "min_percent": 76},
            {"letter": "B",  "points": 74.0, "min_percent": 72},
            {"letter": "B-", "points": 70.5, "min_percent": 68},
            {"letter": "C+", "points": 66.0, "min_percent": 64},
            {"letter": "C",  "points": 62.0, "min_percent": 60},
            {"letter": "C-", "points": 57.5, "min_percent": 55},
            {"letter": "D",  "points": 52.5, "min_percent": 50},
            {"letter": "F",  "points": 0.0,  "min_percent": 0},
        ],
    },

    # ── University of Alberta — 4.0 scale ────────────────────────────
    "University of Alberta": {
        "scale_type": "4.0",
        "max_points": 4.0,
        "grades": [
            {"letter": "A+", "points": 4.0, "min_percent": 90},
            {"letter": "A",  "points": 4.0, "min_percent": 85},
            {"letter": "A-", "points": 3.7, "min_percent": 80},
            {"letter": "B+", "points": 3.3, "min_percent": 77},
            {"letter": "B",  "points": 3.0, "min_percent": 73},
            {"letter": "B-", "points": 2.7, "min_percent": 70},
            {"letter": "C+", "points": 2.3, "min_percent": 67},
            {"letter": "C",  "points": 2.0, "min_percent": 63},
            {"letter": "C-", "points": 1.7, "min_percent": 60},
            {"letter": "D+", "points": 1.3, "min_percent": 57},
            {"letter": "D",  "points": 1.0, "min_percent": 53},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── University of Calgary — 4.0 scale ────────────────────────────
    "University of Calgary": {
        "scale_type": "4.0",
        "max_points": 4.0,
        "grades": [
            {"letter": "A+", "points": 4.0, "min_percent": 95},
            {"letter": "A",  "points": 4.0, "min_percent": 85},
            {"letter": "A-", "points": 3.7, "min_percent": 80},
            {"letter": "B+", "points": 3.3, "min_percent": 77},
            {"letter": "B",  "points": 3.0, "min_percent": 73},
            {"letter": "B-", "points": 2.7, "min_percent": 70},
            {"letter": "C+", "points": 2.3, "min_percent": 67},
            {"letter": "C",  "points": 2.0, "min_percent": 63},
            {"letter": "C-", "points": 1.7, "min_percent": 60},
            {"letter": "D+", "points": 1.3, "min_percent": 57},
            {"letter": "D",  "points": 1.0, "min_percent": 53},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },

    # ── University of Guelph — percentage-based (4.0 scale with +/-)
    "University of Guelph": {
        "scale_type": "4.0",
        "max_points": 4.0,
        "grades": [
            {"letter": "A+", "points": 4.0, "min_percent": 90},
            {"letter": "A",  "points": 4.0, "min_percent": 85},
            {"letter": "A-", "points": 3.7, "min_percent": 80},
            {"letter": "B+", "points": 3.3, "min_percent": 77},
            {"letter": "B",  "points": 3.0, "min_percent": 73},
            {"letter": "B-", "points": 2.7, "min_percent": 70},
            {"letter": "C+", "points": 2.3, "min_percent": 67},
            {"letter": "C",  "points": 2.0, "min_percent": 63},
            {"letter": "C-", "points": 1.7, "min_percent": 60},
            {"letter": "D+", "points": 1.3, "min_percent": 57},
            {"letter": "D",  "points": 1.0, "min_percent": 53},
            {"letter": "D-", "points": 0.7, "min_percent": 50},
            {"letter": "F",  "points": 0.0, "min_percent": 0},
        ],
    },
}


def get_scale(university: str | None) -> tuple[dict, bool]:
    """Return (scale_dict, using_fallback) for a given university name."""
    if university and university in GRADING_SCALES:
        return GRADING_SCALES[university], False
    return FALLBACK_SCALE, True


def build_grade_map(scale: dict) -> dict[str, float]:
    """Build a case-insensitive letter → points lookup from a scale."""
    mapping = {}
    for g in scale["grades"]:
        mapping[g["letter"].upper()] = g["points"]
    return mapping


def map_percent_to_grade(scale: dict, percent: float) -> tuple[str | None, float | None]:
    """Map a percentage (0-100) to a (letter, gpa_points) pair using the scale's
    percentage boundaries. Returns (None, None) if the scale lacks ``min_percent``
    boundaries (degrade gracefully rather than guess)."""
    grades = scale.get("grades", [])
    if not grades or any("min_percent" not in g for g in grades):
        return None, None
    # Highest min_percent that the percentage still clears wins.
    for g in sorted(grades, key=lambda g: g["min_percent"], reverse=True):
        if percent >= g["min_percent"]:
            return g["letter"], g["points"]
    # Below every boundary — fall back to the lowest grade.
    lowest = min(grades, key=lambda g: g["min_percent"])
    return lowest["letter"], lowest["points"]
