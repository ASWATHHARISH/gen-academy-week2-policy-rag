import pytest
from app.scope import personal_legal_entitlement
from app.config import Settings
from app.graph import run_query


@pytest.mark.parametrize("query", [
    "How many paid sick days am I legally entitled to?",
    "What are my statutory annual leave entitlements in France?",
    "What minimum leave does the law guarantee employees?",
    "Are we legally entitled to severance pay?",
])
def test_personal_legal_entitlements_are_outside_policy_scope(query):
    assert personal_legal_entitlement(query)


@pytest.mark.parametrize("query", [
    "What is the GitLab sick-time policy?",
    "What is the minimum password length?",
    "Does the Legal Department approve facilitating payments?",
    "What training must employees complete?",
])
def test_policy_and_legal_department_questions_remain_in_scope(query):
    assert not personal_legal_entitlement(query)


def test_scope_guard_stops_before_retrieval_and_generation(tmp_path):
    def never(*args):
        raise AssertionError("Must stop before retrieval or Gemini")
    cfg = Settings(_env_file=None, gate_mode="p1", calibration_path=tmp_path / "none.json")
    result = run_query("How many paid sick days am I legally entitled to?", cfg, retriever=never, generator=never)
    assert result["status"] == "fallback"
    assert result["reason"] == "personal_legal_entitlement_out_of_scope"
    assert result["api_called"] is False
    assert result["trace"] == ["validate_question", "fallback"]
