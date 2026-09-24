import json
from pathlib import Path

from evaluation.evaluate import load_questions, normalize
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_dataset_size_and_calibration_separation():
    final = load_questions(ROOT / "evaluation" / "questions.json")
    development = load_questions(ROOT / "evaluation" / "calibration.json")
    assert len(final) == 15
    assert sum(row["expected_behavior"] == "answer" for row in final) == 9
    assert len(development) == 6
    assert not {row["question"] for row in final} & {row["question"] for row in development}


def test_gold_passages_exist_in_saved_source_and_whole_chunks():
    chunk_file = ROOT / "data" / "processed" / "chunks.jsonl"
    if not chunk_file.exists():
        pytest.skip("Run ingestion for snapshot-dependent gold audit")
    chunks = [json.loads(line) for line in chunk_file.read_text(encoding="utf-8").splitlines()]
    for name in ("questions", "calibration"):
        for question in load_questions(ROOT / "evaluation" / f"{name}.json"):
            for gold in question.get("gold", []):
                doc = json.loads((chunk_file.parent / (gold["document_id"] + ".json")).read_text(encoding="utf-8"))
                quote = normalize(gold["quote"])
                assert any(quote in normalize(section["text"]) for section in doc["sections"]), question["id"]
                assert any(chunk["metadata"]["document_id"] == gold["document_id"] and quote in normalize(chunk["text"]) for chunk in chunks), question["id"]
