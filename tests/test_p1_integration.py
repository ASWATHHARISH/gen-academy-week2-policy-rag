"""Hybrid -> P1 gate -> quotation/citation checks, with no external services."""
import math
from types import SimpleNamespace

import pytest

from app.bm25 import BM25Index
from app.graph import run_query
from app import retrieval


def fixture(tmp_path, monkeypatch, dense_score=0.9, missing_vector=False):
    dense = {"id": "remote-1", "text": "Remote working requires an approved location.",
             "metadata": {"document_id": "remote", "title": "Remote policy",
                          "source_url": "https://handbook.gitlab.com/remote/"}, "score": dense_score}
    sparse = {"id": "access-1", "text": "MFA is required for access.",
              "metadata": {"document_id": "access", "title": "Access policy",
                           "section": "Authentication", "snapshot_date": "2026-09-24",
                           "source_url": "https://handbook.gitlab.com/security/",
                           "section_url": "https://handbook.gitlab.com/security/#authentication"}}
    class Collection:
        def get(self, ids, include):
            return ({"ids": [], "embeddings": []} if missing_vector else
                    {"ids": ["access-1"], "embeddings": [[0.2, math.sqrt(0.96)]]})
    sparse_index = BM25Index([dense, sparse])
    monkeypatch.setattr(retrieval, "_dense_query", lambda *args, **kwargs:
                        ([dense], Collection(), [1.0, 0.0], {"index_sha256": "fixture"}))
    monkeypatch.setattr(retrieval, "_load_bm25", lambda *args: sparse_index)
    return SimpleNamespace(chunks_path=tmp_path / "chunks.jsonl",
                           calibration_path=tmp_path / "none.json", evidence_threshold=0.6567558,
                           retrieval_mode="hybrid", gate_mode="p1", evidence_k=5)


def forbidden_generator(*args):
    raise AssertionError("The generator should not be reached")


def test_complementary_sparse_passage_keeps_real_score_and_citation_metadata(tmp_path, monkeypatch):
    cfg = fixture(tmp_path, monkeypatch)
    seen = []
    def fake_generator(query, evidence, settings):
        seen.extend(evidence)
        return {"sufficient": True, "claims": [{"text": "MFA is required for access.",
                "chunk_ids": ["access-1"], "quotes": [{"chunk_id": "access-1", "text": "MFA is required for access."}]}]}
    result = run_query("Is MFA required?", cfg, generator=fake_generator)
    assert result["status"] == "answered"
    assert "retrieve_hybrid_rrf" in result["trace"]
    sparse = next(row for row in seen if row["id"] == "access-1")
    assert sparse["score"] == pytest.approx(0.2)
    assert sparse["dense_score"] == pytest.approx(0.2)
    assert sparse["bm25_score"] > 0
    assert sparse["dense_rank"] is None and sparse["sparse_rank"] == 1
    citation = result["citations"][0]
    assert citation["title"] == "Access policy"
    assert citation["url"] == "https://handbook.gitlab.com/security/#authentication"
    assert citation["section"] == "Authentication"
    assert citation["quotes"] == ["MFA is required for access."]


def test_positive_sparse_and_rrf_scores_do_not_bypass_cosine_gate(tmp_path, monkeypatch):
    cfg = fixture(tmp_path, monkeypatch, dense_score=0.5)
    result = run_query("Is MFA required?", cfg, generator=forbidden_generator)
    assert result["status"] == "fallback"
    assert result["api_called"] is False
    assert "grounded_generation" not in result["trace"]


def test_missing_sparse_vector_is_error_without_generation(tmp_path, monkeypatch):
    cfg = fixture(tmp_path, monkeypatch, missing_vector=True)
    result = run_query("Is MFA required?", cfg, generator=forbidden_generator)
    assert result["status"] == "error"
    assert result["reason"] == "sparse_embedding_missing"
    assert result["api_called"] is False
    assert result["citations"] == []


def test_excluded_sixth_candidate_cannot_open_selected_evidence_gate(tmp_path):
    cfg = SimpleNamespace(calibration_path=tmp_path / "none.json", evidence_threshold=0.6567558,
                          retrieval_mode="hybrid", gate_mode="p1", evidence_k=5)
    hits = [{"id": f"chunk-{index}", "text": f"Distinct policy passage {index}.",
             "metadata": {"document_id": f"document-{index}", "title": f"Policy {index}",
                          "source_url": f"https://handbook.gitlab.com/policy-{index}/"},
             "score": 0.8 if index == 5 else 0.6} for index in range(6)]
    result = run_query("What policy applies?", cfg,
                       retriever=lambda *args: hits, generator=forbidden_generator)
    assert result["status"] == "fallback"
    assert result["api_called"] is False
    assert "grounded_generation" not in result["trace"]
