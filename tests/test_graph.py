import json

from app.config import Settings
from app.generation import GenerationError, provider_error_code
from app.graph import run_query
from app.budget import BudgetError, reserve_attempt
from app.retrieval import RetrievalError, deduplicate_evidence, effective_threshold, index_fingerprint, validate_index_manifest
import pytest


def settings(tmp_path):
    return Settings(_env_file=None, google_api_key="", calibration_path=tmp_path / "calibration.json",
                    chunks_path=tmp_path / "chunks.jsonl", api_budget_path=tmp_path / "budget.json",
                    retrieval_mode="dense", gate_mode="p0")


def hit(score=0.9):
    return {"id": "doc-1", "text": "Manager approval is required.", "score": score,
            "metadata": {"document_id": "doc", "title": "Policy",
                         "source_url": "https://handbook.gitlab.com/policy/"}}


def generated(*args):
    return {"sufficient": True, "claims": [{"text": "Manager approval is required.",
            "chunk_ids": ["doc-1"], "quotes": [{"chunk_id": "doc-1", "text": "Manager approval is required."}]}]}


def never_generate(*args):
    raise AssertionError("Generation must not run")


@pytest.mark.parametrize("results", [[], [hit(0.2)]])
def test_no_evidence_never_calls_generation(tmp_path, results):
    result = run_query("What approval is required?", settings(tmp_path),
                       retriever=lambda *args: results, generator=never_generate)
    assert result["status"] == "fallback"
    assert result["api_called"] is False
    assert "grounded_generation" not in result["trace"]


def test_supported_route_and_citations(tmp_path):
    result = run_query("What approval is required?", settings(tmp_path),
                       retriever=lambda *args: [hit()], generator=generated)
    assert result["status"] == "answered"
    assert result["citations"][0]["chunk_id"] == "doc-1"
    assert result["trace"][-1] == "validate_citations"
    assert "draft" not in result


def test_provider_failure_is_error_not_abstention(tmp_path):
    def failure(*args):
        raise GenerationError("gemini_request_failed", api_called=True)
    result = run_query("What approval is required?", settings(tmp_path),
                       retriever=lambda *args: [hit()], generator=failure)
    assert result["status"] == "error"
    assert result["api_called"] is True
    assert result["reason"] == "gemini_request_failed"


def test_generated_missing_support_falls_back(tmp_path):
    result = run_query("What approval is required?", settings(tmp_path),
                       retriever=lambda *args: [hit()], generator=lambda *args: {"sufficient": True, "claims": []})
    assert result["status"] == "fallback"
    assert result["citations"] == []


def test_hard_budget_cannot_be_raised_in_settings(tmp_path):
    cfg = settings(tmp_path).model_copy(update={"max_api_attempts": 999})
    cfg.api_budget_path.write_text(json.dumps({"attempts": 30, "last_attempt_at": 0}), encoding="utf-8")
    with pytest.raises(BudgetError, match="api_budget_exhausted"):
        reserve_attempt(cfg)


def test_corrupt_budget_fails_closed(tmp_path):
    cfg = settings(tmp_path)
    cfg.api_budget_path.write_text("corrupt", encoding="utf-8")
    with pytest.raises(BudgetError, match="api_budget_invalid"):
        reserve_attempt(cfg)


def test_stale_calibration_not_used(tmp_path):
    cfg = settings(tmp_path)
    cfg.calibration_path.write_text(json.dumps({"embedding_model": "other", "threshold": 0.1}), encoding="utf-8")
    assert effective_threshold(cfg) == cfg.evidence_threshold


def test_incomplete_index_fails_closed(tmp_path):
    with pytest.raises(RetrievalError, match="index_incomplete"):
        validate_index_manifest(settings(tmp_path))


def test_duplicate_chunks_cannot_fill_evidence_slots():
    first = hit()
    second = {**first, "id": "doc-2"}
    distinct = {**first, "id": "doc-3", "text": "Expenses are submitted through the finance portal."}
    assert [row["id"] for row in deduplicate_evidence([first, second, distinct])] == ["doc-1", "doc-3"]


def test_gate_sends_at_most_five_passages(tmp_path):
    rows = [{"id": f"doc-{i}", "text": f"Unique policy excerpt {i}", "score": 0.9,
             "metadata": {"document_id": f"doc-{i}"}} for i in range(10)]
    sizes = []
    def count_inputs(query, selected, cfg):
        sizes.append(len(selected))
        return {"sufficient": False, "claims": []}
    result = run_query("What is the policy?", settings(tmp_path),
                       retriever=lambda *args: rows, generator=count_inputs)
    assert sizes == [5]
    assert result["status"] == "fallback"


@pytest.mark.parametrize("status,expected", [(400, "gemini_invalid_request"),
    (401, "gemini_authentication_failed"), (403, "gemini_permission_denied"),
    (404, "gemini_model_not_found"), (429, "gemini_rate_limited"),
    (503, "gemini_provider_unavailable")])
def test_provider_diagnosis_uses_numeric_status_not_message(status, expected):
    class ProviderFailure(Exception):
        code = status
        def __str__(self):
            raise AssertionError("Provider exception text must never be read")
    assert provider_error_code(ProviderFailure()) == expected


def test_provider_diagnosis_follows_cause_without_reading_text():
    root = RuntimeError("Sensitive message must not be printed")
    root.status_code = 429
    wrapped = RuntimeError("Wrapped sensitive message")
    wrapped.__cause__ = root
    assert provider_error_code(wrapped) == "gemini_rate_limited"


def test_calibrated_abstain_all_threshold_is_preserved(tmp_path):
    cfg = settings(tmp_path)
    cfg.chunks_path.write_text("fixture", encoding="utf-8")
    cfg.calibration_path.write_text(json.dumps({
        "embedding_model": cfg.embedding_model, "collection_name": cfg.collection_name,
        "index_sha256": index_fingerprint(cfg), "threshold": 1.000001,
    }), encoding="utf-8")
    assert effective_threshold(cfg) == 1.000001
    result = run_query("What approval is required?", cfg,
                       retriever=lambda *args: [hit(1.0)], generator=never_generate)
    assert result["status"] == "fallback"
    assert result["api_called"] is False


def test_generation_uses_one_attempt_and_no_application_retries(tmp_path, monkeypatch):
    import sys
    import types
    import app.generation as generation_module
    captured = {"invocations": 0, "reservations": 0}
    class FakeModel:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs
        def with_structured_output(self, schema, method):
            assert method == "json_schema"
            return self
        def invoke(self, messages):
            captured["invocations"] += 1
            error = RuntimeError("Do not print a provider message")
            error.code = 429
            raise error
    fake_module = types.ModuleType("langchain_google_genai")
    fake_module.ChatGoogleGenerativeAI = FakeModel
    monkeypatch.setitem(sys.modules, "langchain_google_genai", fake_module)
    def reserve(cfg):
        captured["reservations"] += 1
    monkeypatch.setattr(generation_module, "reserve_attempt", reserve)
    cfg = settings(tmp_path).model_copy(update={
        "google_api_key": __import__("pydantic").SecretStr("offline-test-key"),
        "gemini_free_tier_confirmed": True,
    })
    with pytest.raises(GenerationError, match="gemini_rate_limited") as raised:
        generation_module.generate("What approval?", [hit()], cfg)
    assert raised.value.api_called is True
    assert captured["kwargs"]["max_retries"] == 1
    assert captured["kwargs"]["timeout"] == 45
    assert captured["kwargs"]["vertexai"] is False
    assert captured["invocations"] == captured["reservations"] == 1


def test_installed_gemini_sdk_maps_retry_and_timeout_without_network(monkeypatch):
    from langchain_core.messages import HumanMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    import langchain_google_genai.chat_models as chat_models
    from pydantic import SecretStr
    class NoNetworkClient:
        def __init__(self, **kwargs):
            pass
        def close(self):
            pass
    # Client construction is replaced entirely; only request preparation runs.
    monkeypatch.setattr(chat_models, "Client", NoNetworkClient)
    model = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite", api_key=SecretStr("offline-test-key"),
        vertexai=False, max_retries=1, timeout=45, max_output_tokens=1536,
    )
    request = model._prepare_request([HumanMessage(content="Offline configuration test")])
    options = request["config"].http_options
    assert options.retry_options.attempts == 1
    assert options.timeout == 45000
