"""A bad answer from the model must not be reported as a bad document.

Uploading the real York checklist produced "Could not parse document. Please
ensure it is a valid degree checklist or transcript." The document was fine —
5,791 characters, extracted cleanly, and it parses correctly on a retry. The
failures were a rate limit and an unusable completion, and both told the student
to go and fix a file that was never the problem.
"""
import json

import pytest

from app.services import document_parser as dp
from app.services.document_parser import (
    EmptyModelOutputError,
    ModelOutputError,
    TruncatedModelOutputError,
    parse_degree_document,
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content, reason):
        self.message = _Msg(content)
        self.finish_reason = reason


class _Resp:
    def __init__(self, content, reason="stop"):
        self.choices = [_Choice(content, reason)]


def _patch(monkeypatch, response):
    monkeypatch.setattr(dp, "get_groq_client", lambda: object())
    monkeypatch.setattr(dp, "_spreadsheet_to_text", lambda b, m: "Sheet1\n" + "row\n" * 40)

    async def fake_complete(client, **kwargs):
        return response

    monkeypatch.setattr(dp, "acomplete", fake_complete)


async def test_truncated_completion_says_so(monkeypatch):
    _patch(monkeypatch, _Resp('{"requirements": [], "cour', reason="length"))
    with pytest.raises(TruncatedModelOutputError) as exc:
        await parse_degree_document(b"x", XLSX)
    msg = str(exc.value)
    assert "cut off" in msg
    assert "valid degree checklist" not in msg, "still blaming the document"


async def test_empty_completion_is_reported_as_ours(monkeypatch):
    _patch(monkeypatch, _Resp("", reason="stop"))
    with pytest.raises(EmptyModelOutputError) as exc:
        await parse_degree_document(b"x", XLSX)
    assert "our side" in str(exc.value)


async def test_non_json_completion_does_not_accuse_the_document(monkeypatch):
    _patch(monkeypatch, _Resp("Sure! Here is the checklist you asked for.", reason="stop"))
    with pytest.raises(ModelOutputError) as exc:
        await parse_degree_document(b"x", XLSX)
    assert "try the upload again" in str(exc.value).lower()


async def test_valid_json_still_parses(monkeypatch):
    payload = {"requirements": [], "courses": [
        {"course_code": "LE/EECS 1022", "course_name": "OOP", "credit_value": 3.0,
         "status": "completed", "completion_evidence": "Passed: True"},
    ]}
    _patch(monkeypatch, _Resp(json.dumps(payload), reason="stop"))
    out = await parse_degree_document(b"x", XLSX)
    assert out["courses"][0]["status"] == "completed"


def test_truncation_and_empty_are_both_model_output_errors():
    """The router keys off the base class, so both must inherit it."""
    assert issubclass(TruncatedModelOutputError, ModelOutputError)
    assert issubclass(EmptyModelOutputError, ModelOutputError)
    assert issubclass(ModelOutputError, ValueError)
