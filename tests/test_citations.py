import pytest

from app.citations import CitationValidationError, validate_and_render


def evidence():
    return [{"id": "leave-1", "text": "Approval is required.\nEmployees must ask their manager.",
             "metadata": {"document_id": "leave", "title": "Leave policy",
                          "source_url": "https://handbook.gitlab.com/leave/"}, "score": 0.9}]


def draft():
    return {"sufficient": True, "claims": [{"text": "Employees must ask their manager.",
            "chunk_ids": ["leave-1"], "quotes": [{"chunk_id": "leave-1", "text": "Employees must ask their manager."}]}]}


def test_supported_claim_has_metadata_link():
    answer, citations = validate_and_render(draft(), evidence())
    assert "[1](https://handbook.gitlab.com/leave/)" in answer
    assert citations[0]["title"] == "Leave policy"


def test_invented_source_is_rejected():
    data = draft()
    data["claims"][0]["chunk_ids"] = ["imaginary"]
    with pytest.raises(CitationValidationError, match="unknown_support_id"):
        validate_and_render(data, evidence())


def test_quotation_from_wrong_chunk_is_rejected():
    data = draft()
    data["claims"][0]["quotes"][0]["text"] = "No approval is required."
    with pytest.raises(CitationValidationError, match="quote_not_in_source"):
        validate_and_render(data, evidence())


def test_missing_quote_is_rejected():
    data = draft()
    data["claims"][0]["quotes"] = []
    with pytest.raises(CitationValidationError, match="missing_support_quotes"):
        validate_and_render(data, evidence())


def test_only_whitespace_is_normalized():
    data = draft()
    data["claims"][0]["quotes"][0]["text"] = "Approval is required. Employees must ask their manager."
    validate_and_render(data, evidence())
    data["claims"][0]["quotes"][0]["text"] = "approval is required."
    with pytest.raises(CitationValidationError):
        validate_and_render(data, evidence())

