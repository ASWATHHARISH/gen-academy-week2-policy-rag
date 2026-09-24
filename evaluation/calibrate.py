"""Choose a conservative retrieval threshold using development questions only."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from app.config import ROOT, get_settings
from evaluation.evaluate import load_questions


def main() -> None:
    from app.retrieval import retrieve_documents
    settings = get_settings()
    path = ROOT / "evaluation" / "calibration.json"
    rows = []
    for question in load_questions(path):
        candidates = retrieve_documents(question["question"], settings)
        score = candidates[0]["score"] if candidates else -1.0
        rows.append({"id": question["id"], "question": question["question"],
                     "expected_behavior": question["expected_behavior"], "top_score": float(score)})
    positives = [r["top_score"] for r in rows if r["expected_behavior"] == "answer"]
    negatives = [r["top_score"] for r in rows if r["expected_behavior"] == "fallback"]
    if not positives or not negatives:
        raise ValueError("Calibration requires supported and unsupported development questions")
    # Choose the smallest boundary above every unsupported development score.
    # If classes overlap, report the resulting conservative false rejections.
    threshold = min(1.000001, max(negatives) + 0.0001)
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "embedding_model": settings.embedding_model, "collection_name": settings.collection_name,
              "index_sha256": hashlib.sha256(settings.chunks_path.read_bytes()).hexdigest(),
              "threshold": threshold,
              "method": "Minimum threshold above all unsupported development-query top scores; no test-set tuning.",
              "supported_development_accepted": sum(s >= threshold for s in positives),
              "supported_development_total": len(positives),
              "unsupported_development_accepted": sum(s >= threshold for s in negatives),
              "unsupported_development_total": len(negatives),
              "limitation": "Small calibration set. Similarity gates relevance, not factual support or probability of correctness.",
              "rows": rows}
    settings.calibration_path.parent.mkdir(parents=True, exist_ok=True)
    settings.calibration_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
