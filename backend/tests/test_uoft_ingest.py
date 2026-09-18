"""Tests for the University of Toronto calendar JSON:API adapter.

Hermetic — responses come from an ``httpx.MockTransport``. The node shape below
is the real one returned by
``https://artsci.calendar.utoronto.ca/jsonapi/node/courses``, including the HTML
prerequisite prose with its embedded ``<a href>`` links.
"""
import httpx

from app.ingest import uoft


def _node(title, name, prereq=None):
    return {
        "type": "node--courses",
        "attributes": {
            "title": title,
            "field_course_title": {"value": name, "format": "full_html"},
            "field_prerequisite": {"value": prereq} if prereq else None,
            "field_exclusion": None,
        },
    }


def _serve(pages):
    """pages: list of (data, next_url). Returns a patched httpx.Client factory."""
    real_client = httpx.Client
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        idx = min(len(calls) - 1, len(pages) - 1)
        data, nxt = pages[idx]
        body = {"data": data, "links": {"self": {"href": str(request.url)}}}
        if nxt:
            body["links"]["next"] = {"href": nxt}
        return httpx.Response(200, json=body)

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    return factory, calls


def test_credits_come_from_the_code_suffix():
    """UofT encodes the weight in the code: H is 0.5, Y is 1.0. Nothing guessed."""
    assert uoft._parse_code("CSC207H1") == ("CSC 207H1", "CSC", 0.5)
    assert uoft._parse_code("MAT137Y1") == ("MAT 137Y1", "MAT", 1.0)
    assert uoft._parse_code("not a code") is None


def test_campus_digit_is_preserved_so_campuses_stay_distinct():
    """CSC207H1 (St. George), H5 (Mississauga) and H3 (Scarborough) are three
    different offerings and must not collapse into one catalog row."""
    codes = {uoft._parse_code(t)[0] for t in ("CSC207H1", "CSC207H5", "CSC207H3")}
    assert codes == {"CSC 207H1", "CSC 207H5", "CSC 207H3"}


def test_prerequisite_html_is_stripped_and_slashes_mean_or(monkeypatch):
    prereq = (
        "60% or higher in <a href='/course/CSC148H1'>CSC148H1</a>/ 60% or higher in "
        "<a href='https://utm.calendar.utoronto.ca/course/CSC148H5'>CSC148H5</a>"
    )
    factory, _ = _serve([([_node("CSC207H1", "Software Design", prereq)], None)])
    monkeypatch.setattr(uoft.httpx, "Client", factory)

    rows = uoft.fetch_courses(["artsci"], throttle=0)
    assert len(rows) == 1
    row = rows[0]
    assert row["course_name"] == "Software Design"
    assert row["credits"] == 0.5
    # One OR group: either intro course satisfies it. An AND here would tell a
    # student who took the Mississauga course that they are not eligible.
    assert row["prerequisites"] == [["CSC 148H1", "CSC 148H5"]]
    # The href must not contribute a second copy of the code.
    assert len(row["prerequisites"][0]) == 2


def test_pagination_follows_links_next(monkeypatch):
    pages = [
        ([_node("CSC108H1", "Intro")], "https://artsci.calendar.utoronto.ca/next"),
        ([_node("CSC148H1", "Intro II")], None),
    ]
    factory, calls = _serve(pages)
    monkeypatch.setattr(uoft.httpx, "Client", factory)

    rows = uoft.fetch_courses(["artsci"], throttle=0)
    assert {r["course_code"] for r in rows} == {"CSC 108H1", "CSC 148H1"}
    assert len(calls) == 2 and calls[1].endswith("/next")


def test_pagination_stops_at_the_ceiling(monkeypatch):
    """A next-link that never ends must not walk forever against someone else's
    server."""
    factory, calls = _serve([([_node("CSC108H1", "Intro")], "https://artsci.calendar.utoronto.ca/loop")])
    monkeypatch.setattr(uoft.httpx, "Client", factory)
    monkeypatch.setattr(uoft, "_MAX_PAGES", 3)

    uoft.fetch_courses(["artsci"], throttle=0)
    assert len(calls) == 3


def test_unparseable_titles_are_dropped_not_guessed(monkeypatch):
    factory, _ = _serve([([
        _node("CSC108H1", "Intro"),
        _node("Program Requirements", "Not a course"),
        {"attributes": {}},
    ], None)])
    monkeypatch.setattr(uoft.httpx, "Client", factory)

    rows = uoft.fetch_courses(["artsci"], throttle=0)
    assert [r["course_code"] for r in rows] == ["CSC 108H1"]


def test_http_error_yields_no_rows(monkeypatch):
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(
            lambda r: httpx.Response(503)), **kwargs)

    monkeypatch.setattr(uoft.httpx, "Client", factory)
    assert uoft.fetch_courses(["artsci"], throttle=0) == []


def test_unknown_campus_is_skipped(monkeypatch):
    factory, calls = _serve([([_node("CSC108H1", "Intro")], None)])
    monkeypatch.setattr(uoft.httpx, "Client", factory)
    rows = uoft.fetch_courses(["not-a-campus"], throttle=0)
    assert rows == [] and calls == []


def test_graduate_filter_applies_to_the_ingested_codes():
    """UofT's four-digit codes are graduate; the catalog must not offer them to
    undergraduates once ingested."""
    from app.services.eligibility import is_graduate_level

    assert is_graduate_level("CSC 2515H1", uoft.UNIVERSITY)
    assert not is_graduate_level("CSC 207H1", uoft.UNIVERSITY)


# ── UTSC's different code shape ──────────────────────────────────────

def test_utsc_codes_parse_with_the_subject_not_the_level_letter():
    """UTSC writes CSCA08H3: subject CSC, level A (first year), number 08.

    The general UofT pattern read "CSCA" as the subject and then choked on the
    two-digit number, so a full UTSC crawl returned 44 pages and zero courses —
    every one silently dropped as unparseable.
    """
    assert uoft._parse_code("CSCA08H3") == ("CSC A08H3", "CSC", 0.5)
    assert uoft._parse_code("MATA31H3") == ("MAT A31H3", "MAT", 0.5)
    assert uoft._parse_code("ACMB10H3") == ("ACM B10H3", "ACM", 0.5)


def test_utsc_levels_stay_one_subject():
    """CSCA/CSCB/CSCC are first/second/third-year Computer Science. Treating the
    level letter as part of the subject would split one subject into four and
    break the coverage check that decides whether a student's program is in the
    catalog at all."""
    subjects = {uoft._parse_code(c)[1] for c in ("CSCA08H3", "CSCB09H3", "CSCC01H3")}
    assert subjects == {"CSC"}


def test_utsc_shape_does_not_capture_other_schools_codes():
    """The pattern is narrow on purpose — a York or SFU code must not be read as
    a UTSC one."""
    from app.services.document_parser import normalize_course_code

    assert normalize_course_code("MATH 1300") == "SC/MATH 1300"
    assert normalize_course_code("CMPT 105W") == "CMPT 105W"
    assert normalize_course_code("LE/EECS 2101") == "LE/EECS 2101"
    assert normalize_course_code("CSC207H1") == "CSC 207H1"


def test_utsc_codes_round_trip_through_the_normalizer():
    """The adapter's code and the student's own typed code must land on the same
    string, or their course never matches the catalog entry for it."""
    from app.services.document_parser import normalize_course_code, subject_of

    adapter_code = uoft._parse_code("CSCA08H3")[0]
    assert normalize_course_code("CSCA08H3") == adapter_code
    assert normalize_course_code("csca08h3") == adapter_code
    assert subject_of(adapter_code) == "CSC"


def test_utsc_prerequisites_parse():
    from app.ingest.prereq_parser import parse_prerequisites

    assert parse_prerequisites("CSCA08H3 and (MATA31H3 or MATA30H3)") == [
        ["CSC A08H3"], ["MAT A30H3", "MAT A31H3"],
    ]
