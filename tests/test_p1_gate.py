from app.config import Settings
from app.graph import run_query
from evaluation.calibrate_p1 import choose_threshold


def test_development_floor_not_negative_maximum():
    assert abs(choose_threshold([0.8, 0.7, 0.9]) - 0.68) < 1e-9


def test_p1_preserves_complementary_lower_scoring_passage(tmp_path):
    cfg = Settings(_env_file=None, evidence_threshold=0.7, gate_mode="p1", retrieval_mode="hybrid",
                   calibration_path=tmp_path / "missing.json")
    hits = [{"id": "a", "score": 0.8, "text": "First distinct policy evidence", "metadata": {}},
            {"id": "b", "score": 0.6, "text": "Second complementary security requirement", "metadata": {}}]
    seen = []
    def generator(query, evidence, settings):
        seen.extend(item["id"] for item in evidence)
        return {"sufficient": False, "claims": []}
    result = run_query("A two-part question", cfg, retriever=lambda *args: hits, generator=generator)
    assert seen == ["a", "b"]
    assert result["status"] == "fallback"
    assert "retrieve_hybrid_rrf" in result["trace"]


def test_p1_rejects_all_irrelevant_before_generation(tmp_path):
    cfg = Settings(_env_file=None, evidence_threshold=0.7, gate_mode="p1",
                   calibration_path=tmp_path / "missing.json")
    def never(*args):
        raise AssertionError("Generation must not run")
    result = run_query("Unrelated query", cfg, retriever=lambda *args: [
        {"id": "a", "score": 0.2, "text": "irrelevant", "metadata": {}}], generator=never)
    assert result["status"] == "fallback"
    assert result["api_called"] is False
