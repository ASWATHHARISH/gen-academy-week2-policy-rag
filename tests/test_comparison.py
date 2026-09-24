"""Comparison selection must not leak final-test results into configuration choice."""
from copy import deepcopy

import pytest

from evaluation.compare_retrieval import (
    check_separate_sets, choose_configuration, evaluate_split, top_five_context_tokens,
)


def configuration(profile="384", retrieval="hybrid", recall=1.0, hit=1.0, tokens=500, test_recall=0.0):
    return {
        "profile": profile, "retrieval": retrieval,
        "development": {"summary": {"recall_at_5": recall, "hit_at_5": hit,
                                     "mean_top5_context_tokens": tokens}},
        "test": {"summary": {"recall_at_5": test_recall, "hit_at_5": test_recall}},
    }


def test_selection_ignores_final_test_metrics():
    configs = [configuration(recall=0.8, test_recall=0.0),
               configuration(profile="256", recall=0.7, test_recall=1.0)]
    selected = choose_configuration(configs)
    changed_test_scores = deepcopy(configs)
    changed_test_scores[0]["test"] = {"summary": {"recall_at_5": 1.0}}
    changed_test_scores[1]["test"] = {"summary": {"recall_at_5": 0.0}}
    assert selected["profile"] == "384"
    assert choose_configuration(changed_test_scores) == selected


def test_recall_precedes_hit_rate_and_context_cost():
    configs = [configuration(recall=0.9, hit=0.9, tokens=1000),
               configuration(profile="256", recall=0.8, hit=1.0, tokens=100)]
    assert choose_configuration(configs)["profile"] == "384"


def test_hit_rate_precedes_context_cost():
    configs = [configuration(recall=0.7, hit=1.0, tokens=1000),
               configuration(profile="256", recall=0.7, hit=0.8, tokens=100)]
    assert choose_configuration(configs)["profile"] == "384"


def test_context_cost_breaks_equal_quality_tie():
    configs = [configuration(tokens=800), configuration(profile="256", tokens=500)]
    assert choose_configuration(configs)["profile"] == "256"


def test_exact_tie_prefers_384_then_hybrid():
    configs = [configuration(profile="256", retrieval="hybrid"),
               configuration(profile="384", retrieval="dense"), configuration()]
    result = choose_configuration(configs)
    assert (result["profile"], result["retrieval"]) == ("384", "hybrid")


def test_missing_token_metadata_cannot_look_like_smaller_context():
    with pytest.raises(ValueError, match="token_count"):
        top_five_context_tokens([{"metadata": {}}])
    chunks = [{"metadata": {"token_count": 100}} for _ in range(5)]
    chunks.append({"metadata": {"token_count": 9000}})
    assert top_five_context_tokens(chunks) == 500


def test_comparison_excludes_unsupported_queries_from_recall_and_context_mean():
    questions = [
        {"id": "D1", "question": "supported", "expected_behavior": "answer",
         "gold": [{"document_id": "policy", "quote": "first rule"},
                  {"document_id": "policy", "quote": "second rule"}]},
        {"id": "D2", "question": "unsupported", "expected_behavior": "fallback", "gold": []},
    ]

    def retrieve(query, settings):
        return [{"id": "test", "text": "first rule", "metadata": {
            "document_id": "policy", "token_count": 100 if query == "supported" else 900,
        }}]

    report = evaluate_split(questions, retrieve, None)
    assert report["summary"]["recall_at_5"] == 0.5
    assert report["summary"]["hit_at_5"] == 1
    assert report["summary"]["mean_top5_context_tokens"] == 100
    assert report["rows"][1]["recall_at_5"] is None
    assert report["summary"]["question_count"] == 2


def test_development_test_overlap_is_rejected():
    dev = [{"id": "D1", "question": "How does this work?", "expected_behavior": "answer"}]
    duplicate_text = [{"id": "T1", "question": " HOW  does this work? ", "expected_behavior": "answer"}]
    with pytest.raises(ValueError, match="disjoint"):
        check_separate_sets(dev, duplicate_text)


def test_selection_rejects_empty_or_nonfinite_metrics():
    with pytest.raises(ValueError, match="No configurations"):
        choose_configuration([])
    with pytest.raises(ValueError, match="finite"):
        choose_configuration([configuration(tokens=float("nan"))])
