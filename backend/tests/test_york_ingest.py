"""Tests for the York University Kuali catalog adapter.

Hermetic — every response is served by an ``httpx.MockTransport``. The record
shapes below are the real ones returned by
``https://york.kuali.co/api/v1/catalog/...``, including the prerequisite text
buried inside the course description, which is where York publishes it.
"""
import httpx
import pytest

from app.ingest import york


def _listing(*entries):
    return [
        {
            "__catalogCourseId": code,
            "title": title,
            # Real Kuali pids are opaque slug strings with no slashes in them.
            "pid": "pid" + code.replace("/", "").replace(" ", ""),
        }
        for code, title in entries
    ]


def _serve(listing, details, calls=None):
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if calls is not None:
            calls.append(path)
        if path.endswith(f"/courses/{york.CATALOG_ID}"):
            return httpx.Response(200, json=listing)
        pid = path.rsplit("/", 1)[-1]
        if pid in details:
            return httpx.Response(200, json=details[pid])
        return httpx.Response(404)

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    return factory


# ── Prerequisite extraction ──────────────────────────────────────────

def test_prerequisites_come_only_from_the_prerequisite_clause():
    """York's descriptions name other courses in passing, and those are not
    requirements.

    EECS 2030's description opens "continues the separation of concern theme
    introduced in LE/EECS 1020 3.00". Parsing the whole description would turn
    that narrative aside into a hard prerequisite and block a student from a
    course they are entitled to take.
    """
    narrative = (
        "This course continues the separation of concern theme introduced in "
        "LE/EECS 1020 3.00 and LE/EECS 1021 3.00. It covers abstraction."
    )
    assert york.extract_prerequisites(narrative) == []


def test_semicolons_are_separate_requirements_not_alternatives():
    """York writes "A or B; C" for (A or B) AND C.

    Substituting a bare "and" gives the wrong answer, because "or" binds looser
    in the parser: "A or B and C" reads as "A or (B and C)", which would admit a
    student on A alone when York also requires C.
    """
    desc = (
        "Prerequisites: LE/EECS 2030 3.00 or LE/EECS 1030 3.00; LE/EECS 2031 3.00. "
        "Course credit exclusions: none."
    )
    groups = {frozenset(g) for g in york.extract_prerequisites(desc)}
    assert groups == {
        frozenset({"LE/EECS 2030", "LE/EECS 1030"}),
        frozenset({"LE/EECS 2031"}),
    }


def test_prerequisite_codes_keep_yorks_faculty_prefix():
    """The shared parser emits a bare "EECS 2030", but York's catalog is keyed on
    "LE/EECS 2030" — left bare, every prerequisite would point at a code that
    does not exist in the catalog it belongs to."""
    groups = york.extract_prerequisites("Prerequisite: LE/EECS 1022 3.00.")
    assert groups == [["LE/EECS 1022"]]


def test_credit_values_are_not_read_as_course_numbers():
    """Every York code is written with its weight beside it ("LE/EECS 2030 3.00")."""
    groups = york.extract_prerequisites("Prerequisite: SC/MATH 1300 3.00.")
    assert groups == [["SC/MATH 1300"]]


def test_gpa_clause_does_not_break_the_parse():
    """The gate sentence carries a parenthetical — (without second digit "5") —
    which leaves an unbalanced group in the expression tree if not removed."""
    desc = (
        'Prerequisites: cumulative GPA of 4.50 or better over all major EECS '
        'courses (without second digit "5"); LE/EECS 2030 3.00.'
    )
    assert york.extract_prerequisites(desc) == [["LE/EECS 2030"]]


def test_unparseable_prerequisites_yield_nothing():
    assert york.extract_prerequisites("Prerequisite: permission of the department.") == []
    assert york.extract_prerequisites("") == []
    assert york.extract_prerequisites(None) == []


# ── GPA gates ────────────────────────────────────────────────────────

def test_gpa_gate_is_read_from_the_catalog_prose():
    """York states its enrolment gates in words. Reading them here is what makes
    the gate real for every program, instead of EECS being hardcoded and every
    other faculty's gate silently unenforced."""
    gate = york.parse_gpa_gate_prose(
        "cumulative GPA of 4.50 or better over all major EECS courses"
    )
    assert gate == {"scope": "EECS", "min": 4.50}
    assert york.parse_gpa_gate_prose("no gate stated here") is None


def test_gate_matches_the_hand_transcribed_ground_truth():
    """The bundled catalog was transcribed by hand from York's official checklist
    and carries {"scope": "EECS", "min": 4.50}. The ingested gate must agree, or
    one of the two is wrong about the rule that governs an entire major."""
    from app.data.york_cs_catalog import YORK_CS_COURSES

    hand = next(
        c["gpa_gate"] for c in YORK_CS_COURSES if c["course_code"] == "LE/EECS 2030"
    )
    ingested = york.parse_gpa_gate_prose(
        'cumulative GPA of 4.50 or better over all major EECS courses (without '
        'second digit "5")'
    )
    assert ingested == hand


# ── Fetching ─────────────────────────────────────────────────────────

def test_fetch_builds_rows_from_listing_plus_details(monkeypatch):
    listing = _listing(("LE/EECS2030", "Advanced Object Oriented Programming"))
    details = {
        "pidLEEECS2030": {
            "credits": {"value": "3.00", "credits": {"min": "3", "max": "3"}},
            "description": (
                "<p>Prerequisites: LE/EECS 1022 3.00. Advanced OOP.</p>"
            ),
        }
    }
    monkeypatch.setattr(york.httpx, "Client", _serve(listing, details))

    rows = york.fetch_courses(throttle=0)
    assert len(rows) == 1
    row = rows[0]
    assert row["course_code"] == "LE/EECS 2030"
    assert row["credits"] == 3.0
    assert row["subject_faculty"] == "EECS"
    assert row["prerequisites"] == [["LE/EECS 1022"]]


def test_no_details_mode_makes_exactly_one_request(monkeypatch):
    calls: list = []
    listing = _listing(("LE/EECS2030", "Advanced OOP"), ("AP/PSYC1010", "Intro Psych"))
    monkeypatch.setattr(york.httpx, "Client", _serve(listing, {}, calls))

    rows = york.fetch_courses(details=False, throttle=0)
    assert len(calls) == 1, "the whole university should cost one request"
    assert {r["course_code"] for r in rows} == {"LE/EECS 2030", "AP/PSYC 1010"}
    # Without the per-course records there is no real credit value, so the
    # standard one is used — stated, not silently assumed.
    assert all(r["credits"] == 3.0 for r in rows)
    assert all(r["prerequisites"] == [] for r in rows)


def test_subject_filter(monkeypatch):
    listing = _listing(("LE/EECS2030", "Advanced OOP"), ("AP/PSYC1010", "Intro Psych"))
    monkeypatch.setattr(york.httpx, "Client", _serve(listing, {}))

    rows = york.fetch_courses(details=False, throttle=0, subjects=["psyc"])
    assert [r["course_code"] for r in rows] == ["AP/PSYC 1010"]


def test_a_failing_detail_does_not_lose_the_other_courses(monkeypatch):
    """One course that will not load must not cost the other ten thousand."""
    listing = _listing(("LE/EECS2030", "Advanced OOP"), ("AP/PSYC1010", "Intro Psych"))
    details = {"pidAPPSYC1010": {"credits": {"value": "6.00"}, "description": ""}}
    monkeypatch.setattr(york.httpx, "Client", _serve(listing, details))

    rows = york.fetch_courses(throttle=0)
    by_code = {r["course_code"]: r for r in rows}
    assert set(by_code) == {"LE/EECS 2030", "AP/PSYC 1010"}
    assert by_code["AP/PSYC 1010"]["credits"] == 6.0   # real value, and not 3.0
    assert by_code["LE/EECS 2030"]["credits"] == 3.0   # fell back after the 404


def test_non_york_faculty_prefixes_survive(monkeypatch):
    """The catalog covers all of York, not the eight subjects the normalizer can
    reconstruct a prefix for. HH/, AP/ and FA/ codes must round-trip intact."""
    listing = _listing(
        ("HH/PSYC1010", "Introduction to Psychology"),
        ("AP/ECON1000", "Introduction to Microeconomics"),
        ("FA/DANC1500", "Dance History"),
    )
    monkeypatch.setattr(york.httpx, "Client", _serve(listing, {}))

    rows = york.fetch_courses(details=False, throttle=0)
    assert {r["course_code"] for r in rows} == {
        "HH/PSYC 1010", "AP/ECON 1000", "FA/DANC 1500",
    }
    assert {r["subject_faculty"] for r in rows} == {"PSYC", "ECON", "DANC"}


def test_listing_failure_raises_rather_than_writing_an_empty_catalog(monkeypatch):
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(
            lambda r: httpx.Response(503)), **kwargs)

    monkeypatch.setattr(york.httpx, "Client", factory)
    with pytest.raises(httpx.HTTPStatusError):
        york.fetch_courses(details=False, throttle=0)


def test_a_calendar_year_in_prose_is_not_a_course_code():
    """"(prior to Fall 2015)" must not read as a course.

    This one was caught only by checking an ingested row against the
    hand-transcribed catalog. EECS 2030's real prerequisite is "1021 or 1020
    (prior to Fall 2015) or 1022 or 1720". Treating "Fall 2015" as a course code
    kept the parenthetical as meaningful, the parser tokenized FALL 2015 as a
    course, and the resulting bogus group truncated the list to 1020/1021 —
    silently dropping LE/EECS 1022, the route most students actually arrive by,
    and blocking them from a course they are qualified for.

    Nothing crashed and nothing looked wrong; the catalog was simply wrong about
    a prerequisite.
    """
    desc = (
        'Prerequisites: cumulative GPA of 4.50 or better over all major EECS '
        'courses (without second digit "5"); LE/EECS1021 3.00 or LE/EECS 1020 '
        '(prior to Fall 2015) 3.00 or LE/EECS1022 3.00 or LE/EECS 1720 3.00.'
    )
    groups = york.extract_prerequisites(desc)
    assert groups == [[
        "LE/EECS 1020", "LE/EECS 1021", "LE/EECS 1022", "LE/EECS 1720",
    ]]
    # The course the hand-transcribed checklist names must be among them.
    assert "LE/EECS 1022" in groups[0]


def test_commentary_parentheticals_are_still_dropped():
    """The narrowing must not go so far that real commentary survives."""
    desc = 'Prerequisite: LE/EECS 2030 3.00 (or permission of the department).'
    assert york.extract_prerequisites(desc) == [["LE/EECS 2030"]]
