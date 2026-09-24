"""Evaluate a frozen question set. No paid judge or fabricated metrics.

Gold evidence is a source passage, not a chunk identifier. This keeps labels
usable across chunking configurations. Semantic correctness is audited separately.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import time
from datetime import datetime, timezone
from typing import Any

from app.config import ROOT, get_settings


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def load_questions(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = payload["questions"] if isinstance(payload, dict) else payload
    ids = [item["id"] for item in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Question identifiers must be unique")
    for item in questions:
        if item["expected_behavior"] == "answer" and not item.get("gold"):
            raise ValueError(f"Missing gold evidence for {item['id']}")
    return questions


def evidence_metrics(question: dict[str, Any], candidates: list[dict[str, Any]], k: int = 5) -> dict[str, Any]:
    gold = question.get("gold", [])
    if question["expected_behavior"] != "answer":
        return {"hit_at_5": None, "recall_at_5": None, "evidence_found": [], "evidence_total": 0}
    found = []
    for index, passage in enumerate(gold):
        for chunk in candidates[:k]:
            metadata = chunk.get("metadata", {})
            if metadata.get("document_id") != passage["document_id"]:
                continue
            if normalize(passage["quote"]) in normalize(chunk["text"]):
                found.append(index)
                break
    return {"hit_at_5": int(bool(found)), "recall_at_5": len(found) / len(gold),
            "evidence_found": found, "evidence_total": len(gold)}


def build_summary(rows: list[dict[str, Any]], generation: bool) -> dict[str, Any]:
    supported = [r for r in rows if r["expected_behavior"] == "answer"]
    unsupported = [r for r in rows if r["expected_behavior"] == "fallback"]
    retrieval_times = [r["retrieval_seconds"] for r in rows]
    summary: dict[str, Any] = {
        "question_count": len(rows), "answerable_count": len(supported),
        "expected_fallback_count": len(unsupported),
        "hit_at_5": statistics.mean(r["hit_at_5"] for r in supported) if supported else None,
        "recall_at_5": statistics.mean(r["recall_at_5"] for r in supported) if supported else None,
        "retrieval_median_seconds": statistics.median(retrieval_times) if rows else None,
        "retrieval_max_seconds": max(retrieval_times, default=0),
        "semantic_faithfulness": "See separate evidence-review.json; not inferred from citation structure.",
    }
    if generation:
        summary.update({
            "answered_count": sum(r["response"]["status"] == "answered" for r in rows),
            "fallback_count": sum(r["response"]["status"] == "fallback" for r in rows),
            "service_error_count": sum(r["response"]["status"] == "error" for r in rows),
            "correct_fallback_count": sum(r["response"]["status"] == "fallback" for r in unsupported),
            "false_refusal_count": sum(r["response"]["status"] == "fallback" for r in supported),
            "api_called_questions": sum(bool(r["response"].get("api_called")) for r in rows),
            "end_to_end_median_seconds": statistics.median(r["end_to_end_seconds"] for r in rows),
            "end_to_end_max_seconds": max(r["end_to_end_seconds"] for r in rows),
        })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation" / "questions.json")
    parser.add_argument("--retrieval", choices=["dense", "hybrid"], default="dense")
    parser.add_argument("--profile", choices=["384", "256"], default="384")
    parser.add_argument("--gate", choices=["p0", "p1"], default="p0")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from app.retrieval import retrieve
    from app.profiles import settings_for_profile
    settings = settings_for_profile(args.profile, retrieval=args.retrieval, gate=args.gate)
    questions = load_questions(args.questions)
    kind = "retrieval" if args.retrieval_only else "evaluation"
    stem = f"p1_{args.retrieval}_{args.profile}_{kind}" if args.gate == "p1" else f"{args.retrieval}_{kind}"
    destination = args.output or ROOT / "evaluation" / "results" / f"{stem}.json"
    if destination.exists():
        raise FileExistsError("Preserving recorded results. Supply a fresh --output filename for a new run.")
    if not args.retrieval_only:
        from app.graph import run_query
    # Warm local model/index before timing; this warm-up never calls Gemini.
    warm_start = time.perf_counter()
    retrieve("workplace policy", settings)
    cold_start = time.perf_counter() - warm_start
    rows = []
    for question in questions:
        started = time.perf_counter()
        candidates = retrieve(question["question"], settings)
        retrieval_seconds = time.perf_counter() - started
        row = {**question, **evidence_metrics(question, candidates), "retrieval_seconds": round(retrieval_seconds, 4),
               "retrieved": candidates[:5]}
        if not args.retrieval_only:
            started = time.perf_counter()
            row["response"] = run_query(question["question"], settings=settings)
            row["end_to_end_seconds"] = round(time.perf_counter() - started, 4)
        rows.append(row)
        status = row.get("response", {}).get("status", "retrieval-only")
        print(json.dumps({"id": question["id"], "status": status, "hit_at_5": row["hit_at_5"],
                          "recall_at_5": row["recall_at_5"]}), flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "system": args.retrieval,
              "gate_mode": args.gate, "profile": args.profile,
              "generation_evaluated": not args.retrieval_only, "cold_start_seconds": round(cold_start, 4),
              "model": settings.google_model, "embedding_model": settings.embedding_model,
              "collection": settings.collection_name, "chunk_tokens": settings.chunk_tokens,
              "overlap_tokens": settings.overlap_tokens,
              "questions_sha256": hashlib.sha256(args.questions.read_bytes()).hexdigest(),
              "corpus_chunks_sha256": hashlib.sha256(settings.chunks_path.read_bytes()).hexdigest(),
              "summary": build_summary(rows, not args.retrieval_only), "rows": rows}
    if args.gate == "p1":
        report["summary"]["semantic_faithfulness"] = "See p1_evidence_review.json; AI-assisted source inspection is not an independent human score."
        report["comparison_note"] = "P1 is a diagnostic follow-up on the frozen P0 questions, not a newly unseen test set. Retrieval, chunking and gate changes must not be conflated."
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = destination.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "category", "question", "expected_behavior", "status", "hit_at_5", "recall_at_5", "retrieval_seconds", "end_to_end_seconds"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, row.get("response", {}).get(key, "")) for key in writer.fieldnames})
    print(json.dumps({"report": str(destination), "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
