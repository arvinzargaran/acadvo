"""Tests for the UBC calendar JSON:API adapter.

Hermetic — responses come from an ``httpx.MockTransport``. The node shape is the
real one from ``https://vancouver.calendar.ubc.ca/jsonapi/node/course``.
"""
import httpx

from app.ingest import ubc


def _node(title, credit="(3)", description=None):
    return {
        "type": "node--course",
        "attributes": {
            "title": title,
            "field_course_credit": credit,
            "field_course_description": {"value": description} if description else None,
        },
    }


def _serve(pages):
    real_client = httpx.Client
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        data, nxt = pages[min(len(calls) - 1, len(pages) - 1)]
        body = {"data": data, "links": {"self": {"href": str(request.url)}}}
        if nxt:
            body["links"]["next"] = {"href": nxt}
        return httpx.Response(200, json=body)

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    return factory, calls


def test_campus_marker_is_preserved():
    """UBC's two campuses share 591 subject-and-number pairs that are DIFFERENT
    courses. Stripping _V/_O would merge every one of them."""
    assert ubc._parse_title("SPAN_V - 201: Elementary Spanish I")[0] == "SPAN_V 201"
    assert ubc._parse_title("SPAN_O - 201: Advanced Beginners' Spanish I")[0] == "SPAN_O 201"


def test_subject_excludes_the_campus_marker():
    """Coverage is checked by subject, so CPSC_V and CPSC_O must both be CPSC —
    otherwise one subject looks like two and a student's program stops matching."""
    assert ubc._parse_title("CPSC_V - 100: Computational Thinking")[1] == "CPSC"
    assert ubc._parse_title("CPSC_O - 111: Computation")[1] == "CPSC"


def test_credits_are_published_and_ranges_take_the_lower_bound():
    """A variable-credit course counted at its maximum would tell a student they
    are closer to graduating than they are."""
    assert ubc._credits("(3)") == 3.0
    assert ubc._credits("(1.5)") == 1.5
    assert ubc._credits("(0)") == 0.0
    assert ubc._credits("(3-6)") == 3.0
    assert ubc._credits("(3-12)") == 3.0
    assert ubc._credits(None) == 3.0   # documented fallback


def test_prerequisites_are_pulled_out_of_the_description():
    """UBC has no prerequisite field; the sentence lives in the description."""
    desc = "Basic ideas of computation. Prerequisite: One of CPSC 110, CPSC 103."
    assert ubc._prerequisites(desc, "_V") == [["CPSC_V 103", "CPSC_V 110"]]


def test_prerequisites_are_qualified_to_the_courses_own_campus():
    """A bare code inside the Okanagan calendar means the Okanagan course. Left
    bare it would resolve to Vancouver's, telling an Okanagan student they had
    met a requirement with a course from a campus they do not attend."""
    desc = "Prerequisite: One of CPSC 110, CPSC 103."
    assert ubc._prerequisites(desc, "_O") == [["CPSC_O 103", "CPSC_O 110"]]


def test_corequisites_are_not_swallowed_into_the_prerequisite():
    desc = "Stuff. Prerequisite: CPSC 110. Corequisite: MATH 100."
    groups = ubc._prerequisites(desc, "_V")
    flat = {c for g in groups for c in g}
    assert "CPSC_V 110" in flat
    assert not any("MATH" in c for c in flat), "corequisite leaked into prerequisites"


def test_description_without_prerequisites_yields_none():
    assert ubc._prerequisites("A survey course with no stated requirements.", "_V") == []


def test_malformed_calendar_rows_are_dropped(monkeypatch):
    """The live feed carries a couple of broken titles ("- 447:"). Inventing a
    name would put a course in the catalog UBC never described."""
    factory, _ = _serve([([
        _node("CPSC_V - 100: Computational Thinking"),
        _node("- 447:"),
        _node("SLAV_V - 447: "),          # code parses, name empty
        {"attributes": {}},
    ], None)])
    monkeypatch.setattr(ubc.httpx, "Client", factory)

    rows = ubc.fetch_courses(["vancouver"], throttle=0)
    assert [r["course_code"] for r in rows] == ["CPSC_V 100"]


def test_pagination_follows_links_next(monkeypatch):
    pages = [
        ([_node("CPSC_V - 100: Intro")], "https://vancouver.calendar.ubc.ca/next"),
        ([_node("CPSC_V - 110: Systematic Program Design")], None),
    ]
    factory, calls = _serve(pages)
    monkeypatch.setattr(ubc.httpx, "Client", factory)

    rows = ubc.fetch_courses(["vancouver"], throttle=0)
    assert {r["course_code"] for r in rows} == {"CPSC_V 100", "CPSC_V 110"}
    assert len(calls) == 2


def test_http_error_yields_no_rows(monkeypatch):
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(
            lambda r: httpx.Response(503)), **kwargs)

    monkeypatch.setattr(ubc.httpx, "Client", factory)
    assert ubc.fetch_courses(["vancouver"], throttle=0) == []


def test_codes_round_trip_through_the_normalizer():
    """The adapter's code and a student's typed code must land on the same string."""
    from app.services.document_parser import normalize_course_code, subject_of

    code = ubc._parse_title("CPSC_V - 100: Computational Thinking")[0]
    assert normalize_course_code(code) == code
    assert normalize_course_code("cpsc_v 100") == code
    assert subject_of(code) == "CPSC"


def test_bare_code_resolves_to_vancouver_deterministically():
    """A student typing "SPAN 201" cannot say which campus. It must resolve the
    same way every run, not to whichever row the database returned first."""
    from app.services.catalog import Catalog

    catalog = Catalog({
        "SPAN_O 201": {"course_name": "Advanced Beginners' Spanish I"},
        "SPAN_V 201": {"course_name": "Elementary Spanish I"},
    })
    assert catalog["SPAN 201"]["course_name"] == "Elementary Spanish I"
    # An explicit campus is still honoured exactly.
    assert catalog["SPAN_O 201"]["course_name"] == "Advanced Beginners' Spanish I"


def test_ubc_writes_its_own_campus_marker_into_prerequisite_prose():
    """The real miss: UBC states prerequisites already campus-marked.

    "Prerequisite: CPSC_V 213 and either CPSC_V 221 or DSCI_V 221." The parser's
    code pattern matched the subject and then hit an underscore where it wanted a
    digit, so every UBC prerequisite naming a course parsed to nothing — the
    first ingest recorded prerequisites for 15% of courses.
    """
    from app.ingest.prereq_parser import parse_prerequisites

    assert parse_prerequisites("CPSC_V 221 or DSCI_V 221") == [["CPSC_V 221", "DSCI_V 221"]]
    # Already-marked codes must not be re-qualified by the adapter.
    assert ubc._qualify("CPSC_V 221", "_O") == "CPSC_V 221"


def test_high_school_prerequisites_yield_no_course_codes():
    """"Principles of Mathematics 12" is a real UBC prerequisite and is not a
    course in any catalog. It must produce nothing rather than a fabricated code."""
    assert ubc._prerequisites(
        "Stuff. Prerequisite: Principles of Mathematics 12 or Pre-calculus 12.", "_V"
    ) == []


def test_marked_prerequisites_survive_the_full_row_build():
    node = {
        "attributes": {
            "title": "CPSC_V - 313: Computer Hardware and Operating Systems",
            "field_course_credit": "(3)",
            "field_course_description": {
                "value": "Instruction sets. [3-0-1] Prerequisite: CPSC_V 213 and CPSC_V 221."
            },
        }
    }
    row = ubc._row_from_node(node)
    flat = {c for g in row["prerequisites"] for c in g}
    assert flat == {"CPSC_V 213", "CPSC_V 221"}
