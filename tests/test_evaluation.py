"""Metrics must depend on actual evidence, not just matching a document title."""
from evaluation.evaluate import evidence_metrics


def test_multi_evidence_recall_counts_missing_passage():
    question = {"expected_behavior": "answer", "gold": [{"document_id": "a", "quote": "first rule"}, {"document_id": "b", "quote": "second rule"}]}
    candidates = [{"text": "A first rule exists", "metadata": {"document_id": "a"}}]
    result = evidence_metrics(question, candidates)
    assert result["hit_at_5"] == 1
    assert result["recall_at_5"] == 0.5


def test_same_document_without_gold_passage_is_not_a_hit():
    question = {"expected_behavior": "answer", "gold": [{"document_id": "a", "quote": "first rule"}]}
    result = evidence_metrics(question, [{"text": "irrelevant passage", "metadata": {"document_id": "a"}}])
    assert result["hit_at_5"] == 0


def test_unsupported_questions_have_no_retrieval_recall():
    assert evidence_metrics({"expected_behavior": "fallback"}, [])["recall_at_5"] is None
