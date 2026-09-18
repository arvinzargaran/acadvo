"""Tests for the University of Waterloo Open Data (v3) adapter.

Hermetic: every response is served by an ``httpx.MockTransport``, so the suite
never touches Waterloo's API (which is key-gated and rate-limited anyway). The
payload shape below is the real ``Course`` schema from the live OpenAPI document
at https://openapi.data.uwaterloo.ca/swagger/v1/swagger.json — 19 properties,
none of which is a credit or unit field.
"""
import httpx
import pytest

from app.ingest import waterloo


def _course(**over):
    base = {
        "courseId": "011209",
        "courseOfferNumber": 1,
        "termCode": "1259",
        "termName": "Fall 2025",
        "associatedAcademicCareer": "UG",
        "subjectCode": "CS",
        "catalogNumber": "245",
        "title": "Logic and Computation",
        "description": "Propositional and predicate logic.",
        "gradingBasis": "NUM",
        "courseComponentCode": "LEC",
        "requirementsDescription": "Prereq: (MATH 135 or MATH 145) and (CS 136 or CS 146)",
    }
    base.update(over)
    return base


def _client_factory(routes, calls=None):
    """Patch httpx.Client so the adapter talks to ``routes`` (path -> payload)."""
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if calls is not None:
            calls.append((path, request.headers.get("x-api-key")))
        if path not in routes:
            return httpx.Response(404)
        payload = routes[path]
        if isinstance(payload, int):
            return httpx.Response(payload)
        return httpx.Response(200, json=payload)

    # Bind the real class now: monkeypatch replaces the attribute on the shared
    # httpx module, so calling httpx.Client() from inside the factory would
    # re-enter the factory forever.
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    return factory


def test_fetch_courses_maps_the_real_schema(monkeypatch):
    routes = {"/v3/Courses/1259": [_course(), _course(
        courseId="011210", subjectCode="MATH", catalogNumber="135",
        title="Algebra for Honours Mathematics", requirementsDescription=None,
    )]}
    monkeypatch.setattr(waterloo.httpx, "Client", _client_factory(routes))

    rows = waterloo.fetch_courses("1259", "test-key")
    by_code = {r["course_code"]: r for r in rows}
    assert set(by_code) == {"CS 245", "MATH 135"}

    cs = by_code["CS 245"]
    assert cs["course_name"] == "Logic and Computation"
    assert cs["subject_faculty"] == "CS"
    # Prose prerequisites become the app's CNF structure: AND across groups,
    # OR within one.
    assert sorted(sorted(g) for g in cs["prerequisites"]) == [
        ["CS 136", "CS 146"], ["MATH 135", "MATH 145"],
    ]
    # Prose with no codes in it must not invent any.
    assert by_code["MATH 135"]["prerequisites"] == []


def test_every_course_carries_waterloos_standard_unit(monkeypatch):
    """The API publishes no unit field, so rows are written at 0.5 — and that
    number must match the credit model, or the planner and the catalog would
    disagree about the size of a Waterloo course."""
    from app.data.credit_models import get_credit_model

    routes = {"/v3/Courses/1259": [_course()]}
    monkeypatch.setattr(waterloo.httpx, "Client", _client_factory(routes))

    rows = waterloo.fetch_courses("1259", "test-key")
    assert rows[0]["credits"] == 0.5
    assert rows[0]["credits"] == get_credit_model("University of Waterloo").unit


def test_graduate_courses_are_excluded(monkeypatch):
    """Recommending a grad course to an undergrad is an advising failure, and the
    term feed mixes both."""
    routes = {"/v3/Courses/1259": [
        _course(),
        _course(courseId="9", associatedAcademicCareer="GRD", subjectCode="CS",
                catalogNumber="854", title="Advanced Topics"),
    ]}
    monkeypatch.setattr(waterloo.httpx, "Client", _client_factory(routes))

    codes = {r["course_code"] for r in waterloo.fetch_courses("1259", "test-key")}
    assert codes == {"CS 245"}


def test_repeated_offerings_collapse_to_one_row(monkeypatch):
    """A course offered twice in a term appears twice in the feed; the catalog is
    keyed on the code, so a second row would just fight the first in the upsert."""
    routes = {"/v3/Courses/1259": [_course(), _course(courseOfferNumber=2)]}
    monkeypatch.setattr(waterloo.httpx, "Client", _client_factory(routes))

    rows = waterloo.fetch_courses("1259", "test-key")
    assert len(rows) == 1


def test_subject_filter_requests_only_those_subjects(monkeypatch):
    calls: list = []
    routes = {
        "/v3/Courses/1259/CS": [_course()],
        "/v3/Courses/1259/MATH": [_course(subjectCode="MATH", catalogNumber="135",
                                          title="Algebra")],
    }
    monkeypatch.setattr(waterloo.httpx, "Client", _client_factory(routes, calls))

    rows = waterloo.fetch_courses("1259", "test-key", ["cs", " math "])
    assert {r["course_code"] for r in rows} == {"CS 245", "MATH 135"}
    assert [p for p, _ in calls] == ["/v3/Courses/1259/CS", "/v3/Courses/1259/MATH"]
    # The key travels as a header, never in the URL.
    assert all(k == "test-key" for _, k in calls)


def test_missing_key_raises_instead_of_ingesting_nothing():
    """An empty ingest is indistinguishable from 'Waterloo published nothing' and
    would be upserted as a successful ingest of zero courses."""
    with pytest.raises(waterloo.WaterlooAuthError):
        waterloo.fetch_courses("1259", "")


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_key_raises_with_remediation(monkeypatch, status):
    routes = {"/v3/Courses/1259": status}
    monkeypatch.setattr(waterloo.httpx, "Client", _client_factory(routes))

    with pytest.raises(waterloo.WaterlooAuthError) as exc:
        waterloo.fetch_courses("1259", "bad-key")
    assert "WATERLOO_API_KEY" in str(exc.value)


def test_current_term_reads_the_term_code(monkeypatch):
    routes = {"/v3/Terms/current": [{"termCode": "1259", "name": "Fall 2025"}]}
    monkeypatch.setattr(waterloo.httpx, "Client", _client_factory(routes))
    assert waterloo.current_term("test-key") == "1259"


def test_unexpected_payload_yields_no_rows(monkeypatch):
    """A shape change upstream must produce zero rows, not a crash and not
    garbage rows in the catalog."""
    routes = {"/v3/Courses/1259": {"error": "unexpected"}}
    monkeypatch.setattr(waterloo.httpx, "Client", _client_factory(routes))
    assert waterloo.fetch_courses("1259", "test-key") == []
