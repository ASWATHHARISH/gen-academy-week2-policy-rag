"""UI lifecycle tests. Mock graph execution; never contact a model or API."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import app.graph as graph


UI_PATH = Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py"
SOURCE_URL = "https://handbook.gitlab.com/handbook/security/policies_and_standards/password-standard/"
SECTION_URL = SOURCE_URL + "#password-requirements"
QUESTION = "What is the minimum password length?"


def response_fixture(status: str = "answered") -> dict:
    """Synthetic test data exercises rendering; it is not an evaluation result."""
    evidence = [{
        "id": "test-password-1", "text": "Minimum Length = 12 characters", "score": 0.9,
        "metadata": {
            "document_id": "password-standard", "title": "GitLab Password Standards",
            "source_url": SOURCE_URL, "section": "Password Requirements",
            "section_url": SECTION_URL, "snapshot_date": "test-only",
        },
    }]
    citations = [{
        "number": 1, "chunk_id": "test-password-1", "document_id": "password-standard",
        "title": "GitLab Password Standards", "url": SECTION_URL, "source_url": SOURCE_URL,
        "section": "Password Requirements", "snapshot_date": "test-only",
        "quotes": ["Minimum Length = 12 characters"],
    }]
    answers = {
        "answered": f"The minimum is 12 characters. [1]({SECTION_URL})",
        "fallback": "I could not find sufficient evidence in this policy collection.",
        "error": "Service unavailable.",
    }
    return {
        "query": QUESTION, "status": status, "answer": answers[status],
        "citations": citations if status == "answered" else [],
        "evidence": evidence if status == "answered" else [],
        "reason": "" if status == "answered" else "test_failure",
        "latency_seconds": 1.25, "trace": ["test_mock"], "api_called": False,
    }


@pytest.fixture
def graph_call(monkeypatch):
    call = Mock(return_value=response_fixture())
    monkeypatch.setattr(graph, "run_query", call)
    return call


def launch() -> AppTest:
    page = AppTest.from_file(str(UI_PATH), default_timeout=10).run()
    assert not page.exception
    return page


def submit(page: AppTest, question: str = QUESTION) -> AppTest:
    page.text_area[0].input(question)
    page.button[0].click().run()
    assert not page.exception
    return page


def test_startup_is_read_only(graph_call):
    page = launch()
    assert page.title[0].value == "Enterprise Policy Q&A"
    assert page.button[0].label == "Find an answer"
    assert not page.success
    assert not page.error
    graph_call.assert_not_called()


def test_blank_question_does_not_execute_graph(graph_call):
    page = submit(launch(), "  \n  ")
    assert page.warning[0].value == "Enter a policy question first."
    graph_call.assert_not_called()


def test_supported_answer_shows_sources_evidence_and_latency(graph_call):
    page = submit(launch(), f"  {QUESTION}  ")
    graph_call.assert_called_once_with(QUESTION)
    assert page.success[0].value == "Answer with validated source references"
    assert any("The minimum is 12 characters." in item.value for item in page.markdown)
    assert any(item.value == "Sources" for item in page.subheader)
    assert page.expander[0].label == "Inspect retrieved evidence (1 excerpts)"
    assert any(item.value == "Minimum Length = 12 characters" for item in page.text)
    assert any(item.value == "Response time: 1.25 s" for item in page.caption)
    source_links = [item for item in page.get("link_button") if item.proto.label == "Open source section"]
    assert source_links
    assert all(item.proto.url == SECTION_URL for item in source_links)
    assert not page.error


def test_fallback_is_displayed_as_missing_evidence(graph_call):
    graph_call.return_value = response_fixture("fallback")
    page = submit(launch())
    assert "evidence is insufficient" in page.info[0].value
    assert any("could not find sufficient evidence" in item.value for item in page.markdown)
    assert not page.error
    assert not page.success
    assert not page.expander
    graph_call.assert_called_once_with(QUESTION)


def test_service_error_is_distinct_from_policy_fallback(graph_call):
    graph_call.return_value = response_fixture("error")
    page = submit(launch())
    assert "technical issue" in page.error[0].value
    assert any("local model and document index" in item.value for item in page.markdown)
    assert not page.info
    assert not page.success
    assert not page.expander
    graph_call.assert_called_once_with(QUESTION)


def test_rerun_preserves_result_without_executing_graph_again(graph_call):
    page = submit(launch())
    initial_answer = page.session_state["policy_result"]["answer"]
    page.run()
    assert not page.exception
    graph_call.assert_called_once_with(QUESTION)
    assert page.session_state["policy_result"]["answer"] == initial_answer
    assert page.session_state["policy_question"] == QUESTION
    assert any("The minimum is 12 characters." in item.value for item in page.markdown)
    assert page.success[0].value == "Answer with validated source references"
