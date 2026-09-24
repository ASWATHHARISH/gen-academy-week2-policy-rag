"""Calibrate a relevance prefilter on development queries; not answer confidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json

from app.config import ROOT
from evaluation.evaluate import load_questions


def choose_threshold(positive_scores):
    if not positive_scores:
        raise ValueError("Supported development examples are required")
    # Fixed before P1 results: small margin below weakest supported dev query.
    # Unsupported topical questions may pass and must be rejected by grounding.
    return max(-1.0, min(1.0, min(positive_scores) - 0.02))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["384", "256"], required=True)
    parser.add_argument("--retrieval", choices=["dense", "hybrid"], default="hybrid")
    args = parser.parse_args()
    from app.profiles import settings_for_profile
    from app.retrieval import deduplicate_evidence, retrieve
    settings = settings_for_profile(args.profile, retrieval=args.retrieval, gate="p1")
    questions_path = ROOT / "evaluation" / "calibration.json"
    rows = []
    for question in load_questions(questions_path):
        hits = deduplicate_evidence(retrieve(question["question"], settings), min(5, settings.evidence_k))
        rows.append({"id": question["id"], "question": question["question"],
                     "expected_behavior": question["expected_behavior"],
                     "max_cosine": max((hit["score"] for hit in hits), default=-1.0)})
    positives = [row["max_cosine"] for row in rows if row["expected_behavior"] == "answer"]
    negatives = [row["max_cosine"] for row in rows if row["expected_behavior"] == "fallback"]
    threshold = choose_threshold(positives)
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "embedding_model": settings.embedding_model, "collection_name": settings.collection_name,
              "index_sha256": hashlib.sha256(settings.chunks_path.read_bytes()).hexdigest(),
              "development_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
              "retrieval_mode": args.retrieval, "gate_mode": "p1", "threshold": threshold,
              "method": "Minimum supported-development candidate maximum cosine minus a fixed 0.02 margin. Query-level relevance only; retain complementary top-five evidence.",
              "supported_development_accepted": sum(score >= threshold for score in positives),
              "supported_development_total": len(positives),
              "unsupported_development_accepted": sum(score >= threshold for score in negatives),
              "unsupported_development_total": len(negatives),
              "limitation": "Acceptance is not proof of support. Unsupported topical questions can reach Gemini, which must abstain. No test-set scores used in this threshold calculation.",
              "rows": rows}
    settings.calibration_path.parent.mkdir(parents=True, exist_ok=True)
    if settings.calibration_path.exists():
        raise FileExistsError("Preserve existing P1 calibration; inspect before replacing.")
    settings.calibration_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
