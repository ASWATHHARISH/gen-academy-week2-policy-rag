"""Deterministic local retrieval checks; no models, providers or network calls."""
import hashlib
import json
import math
from types import SimpleNamespace

import pytest

from app.bm25 import BM25Index, reciprocal_rank_fusion, tokenize
from app import retrieval


def document(cid, text):
    return {"id": cid, "text": text, "metadata": {"document_id": cid, "title": cid}}


def test_bm25_matches_formula_and_positive_idf():
    index = BM25Index([document("a", "policy policy travel"), document("b", "travel"), document("c", "security")])
    expected_idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
    expected = expected_idf * (2 * 2.5) / (2 + 1.5 * (0.25 + 0.75 * 3 / (5 / 3)))
    assert index.scores("policy")["a"] == pytest.approx(expected)
    assert index.scores("policy")["b"] == 0
    assert index.scores("policy policy") == index.scores("policy")
    common = BM25Index([document("a", "policy"), document("b", "policy")])
    assert common.idf["policy"] > 0


def test_tokenization_preserves_numbers_acronyms_and_negation():
    assert tokenize("The MFA and VPN in 2026 are NOT optional: 2FA.") == ["mfa", "vpn", "2026", "not", "optional", "2fa"]


def test_no_matching_terms_do_not_fabricate_sparse_hits():
    assert BM25Index([]).search("policy") == []
    index = BM25Index([document("a", "remote work"), document("b", "")])
    assert index.search("unmentioned") == []
    assert index.search("the and") == []


def test_rrf_uses_ranks_equal_weights_and_deduplicates_ids():
    rows = reciprocal_rank_fusion(["a", "b", "b"], ["b", "c"])
    assert [row["id"] for row in rows] == ["b", "a", "c"]
    assert rows[0]["rrf_score"] == pytest.approx(1 / 62 + 1 / 61)
    assert rows[0]["dense_rank"] == 2
    assert rows[0]["sparse_rank"] == 1
    assert rows[1]["sparse_rank"] is None


def test_sparse_snapshot_cache_changes_with_corpus_bytes(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text(json.dumps(document("a", "remote work")) + "\n", encoding="utf-8")
    first_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    first = retrieval._load_bm25(str(path), first_hash)
    assert first is retrieval._load_bm25(str(path), first_hash)
    path.write_text(json.dumps(document("b", "VPN access")) + "\n", encoding="utf-8")
    second_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    second = retrieval._load_bm25(str(path), second_hash)
    assert second is not first
    assert second.search("VPN")[0]["id"] == "b"
    with pytest.raises(retrieval.RetrievalError, match="sparse_snapshot_changed"):
        retrieval._load_bm25(str(path), "invalid-fingerprint")


def hybrid_fixture(tmp_path, monkeypatch, missing=False):
    dense = {**document("dense", "Remote working policy"), "score": 0.8}
    sparse = document("sparse", "VPN MFA requirements")
    index = BM25Index([dense, sparse])
    calls = {"dense": 0, "get": 0}
    class Collection:
        def get(self, ids, include):
            calls["get"] += 1
            assert ids == ["sparse"]
            assert include == ["embeddings"]
            if missing:
                return {"ids": [], "embeddings": []}
            return {"ids": ["sparse"], "embeddings": [[-0.5, math.sqrt(0.75)]]}
    def dense_query(query, settings, limit=None):
        calls["dense"] += 1
        assert limit == 10
        return [dense], Collection(), [1.0, 0.0], {"index_sha256": "verified-hash"}
    monkeypatch.setattr(retrieval, "_dense_query", dense_query)
    monkeypatch.setattr(retrieval, "_load_bm25", lambda *args: index)
    cfg = SimpleNamespace(chunks_path=tmp_path / "chunks.jsonl", retrieval_mode="hybrid")
    return cfg, calls


def test_sparse_only_candidate_has_real_cosine_not_fusion_score(tmp_path, monkeypatch):
    cfg, calls = hybrid_fixture(tmp_path, monkeypatch)
    rows = retrieval.retrieve_hybrid("VPN MFA", cfg)
    by_id = {row["id"]: row for row in rows}
    assert by_id["dense"]["score"] == by_id["dense"]["dense_score"] == 0.8
    assert by_id["sparse"]["score"] == pytest.approx(-0.5)
    assert by_id["sparse"]["dense_score"] == pytest.approx(-0.5)
    assert by_id["sparse"]["rrf_score"] == pytest.approx(1 / 61)
    assert by_id["sparse"]["bm25_score"] > 0
    assert by_id["sparse"]["dense_rank"] is None
    assert by_id["dense"]["sparse_rank"] is None
    assert calls == {"dense": 1, "get": 1}


def test_missing_stored_vector_fails_closed(tmp_path, monkeypatch):
    cfg, _ = hybrid_fixture(tmp_path, monkeypatch, missing=True)
    with pytest.raises(retrieval.RetrievalError, match="sparse_embedding_missing"):
        retrieval.retrieve_hybrid("VPN", cfg)


@pytest.mark.parametrize("vector", [[float("nan"), 1], [0, 0], [1]])
def test_invalid_stored_vector_fails_closed(vector):
    with pytest.raises(retrieval.RetrievalError):
        retrieval._cosine_similarity([1, 0], vector)


def test_dispatch_and_dense_api_remain_separate(monkeypatch):
    calls = []
    monkeypatch.setattr(retrieval, "retrieve_documents", lambda q, s: calls.append("dense") or [])
    monkeypatch.setattr(retrieval, "retrieve_hybrid", lambda q, s: calls.append("hybrid") or [])
    retrieval.retrieve("question", SimpleNamespace(retrieval_mode="dense"))
    retrieval.retrieve("question", SimpleNamespace(retrieval_mode="hybrid"))
    assert calls == ["dense", "hybrid"]
    with pytest.raises(retrieval.RetrievalError, match="invalid_retrieval_mode"):
        retrieval.retrieve("question", SimpleNamespace(retrieval_mode="unapproved"))


def test_fused_results_capped_at_ten(tmp_path, monkeypatch):
    dense = [{**document(str(i), f"policy {i}"), "score": 0.8} for i in range(15)]
    index = BM25Index(dense)
    monkeypatch.setattr(retrieval, "_dense_query", lambda *a, **k: (dense[:10], None, [1, 0], {"index_sha256": "hash"}))
    monkeypatch.setattr(retrieval, "_load_bm25", lambda *a: index)
    rows = retrieval.retrieve_hybrid("unmatched", SimpleNamespace(chunks_path=tmp_path / "chunks.jsonl"))
    assert len(rows) == 10
    assert all(row["sparse_rank"] is None for row in rows)


def test_calibration_cannot_cross_retrieval_or_gate_profiles(tmp_path):
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text("fixture", encoding="utf-8")
    calibration = tmp_path / "calibration.json"
    cfg = SimpleNamespace(chunks_path=chunks, calibration_path=calibration,
                          embedding_model="bge", collection_name="policies",
                          evidence_threshold=0.65, retrieval_mode="hybrid", gate_mode="p1")
    baseline = {"embedding_model": "bge", "collection_name": "policies",
                "index_sha256": retrieval.index_fingerprint(cfg), "threshold": 0.42}
    # Missing profile fields describe legacy dense/P0, never P1.
    calibration.write_text(json.dumps(baseline), encoding="utf-8")
    assert retrieval.effective_threshold(cfg) == 0.65
    calibration.write_text(json.dumps({**baseline, "retrieval_mode": "hybrid", "gate_mode": "p0"}), encoding="utf-8")
    assert retrieval.effective_threshold(cfg) == 0.65
    calibration.write_text(json.dumps({**baseline, "retrieval_mode": "dense", "gate_mode": "p1"}), encoding="utf-8")
    assert retrieval.effective_threshold(cfg) == 0.65
    calibration.write_text(json.dumps({**baseline, "retrieval_mode": "hybrid", "gate_mode": "p1"}), encoding="utf-8")
    assert retrieval.effective_threshold(cfg) == 0.42
    cfg.retrieval_mode, cfg.gate_mode = "dense", "p0"
    calibration.write_text(json.dumps(baseline), encoding="utf-8")
    assert retrieval.effective_threshold(cfg) == 0.42
