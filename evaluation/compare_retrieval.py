"""Compare P1 retrieval profiles offline; select using development evidence only.

This module never calls the graph or generator. The inspected P0 test set is a
diagnostic follow-up set, not a newly held-out evaluation for the P1 changes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any, Callable

from app.config import ROOT
from evaluation.evaluate import evidence_metrics, load_questions, normalize


CONFIGURATIONS = (("384", "dense"), ("384", "hybrid"), ("256", "dense"), ("256", "hybrid"))
SELECTION_METHOD = (
    "Development-set mean passage Recall@5 descending, then Hit@5 descending, "
    "then mean top-five context token count on answerable development questions ascending. "
    "Exact remaining ties prefer profile384 for stability, then hybrid for the approved P1 feature. "
    "Final-test results and latency never enter selection."
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_separate_sets(development: list[dict], final_test: list[dict]) -> None:
    """Do not silently select a configuration on a question also called a test."""
    development_ids = {row["id"] for row in development}
    final_ids = {row["id"] for row in final_test}
    development_text = {normalize(row["question"]) for row in development}
    final_text = {normalize(row["question"]) for row in final_test}
    if development_ids & final_ids or development_text & final_text:
        raise ValueError("Development and final-test questions must be disjoint.")
    if not any(row["expected_behavior"] == "answer" for row in development):
        raise ValueError("Development selection requires answerable gold-labelled questions.")


def top_five_context_tokens(candidates: list[dict[str, Any]]) -> int:
    """Use actual tokenizer metadata; a missing count must not look cheaper."""
    counts = []
    for candidate in candidates[:5]:
        count = candidate.get("metadata", {}).get("token_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("Every retrieved chunk needs a non-negative integer token_count.")
        counts.append(count)
    return sum(counts)


def split_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in rows if row["expected_behavior"] == "answer"]
    latencies = [row["retrieval_seconds"] for row in rows]
    return {
        "question_count": len(rows),
        "answerable_count": len(supported),
        "expected_fallback_count": len(rows) - len(supported),
        "hit_at_5": statistics.mean(row["hit_at_5"] for row in supported) if supported else None,
        "recall_at_5": statistics.mean(row["recall_at_5"] for row in supported) if supported else None,
        "mean_top5_context_tokens": statistics.mean(row["top5_context_tokens"] for row in supported) if supported else None,
        "retrieval_median_seconds": statistics.median(latencies) if latencies else None,
        "retrieval_max_seconds": max(latencies, default=0.0),
    }


def evaluate_split(
    questions: list[dict[str, Any]], retriever: Callable, settings: Any,
) -> dict[str, Any]:
    rows = []
    for question in questions:
        started = time.perf_counter()
        candidates = retriever(question["question"], settings)
        elapsed = time.perf_counter() - started
        rows.append({
            **question,
            **evidence_metrics(question, candidates),
            "retrieval_seconds": round(elapsed, 6),
            "top5_context_tokens": top_five_context_tokens(candidates),
            "retrieved": candidates[:5],
        })
    return {"summary": split_summary(rows), "rows": rows}


def choose_configuration(configurations: list[dict[str, Any]]) -> dict[str, Any]:
    """Read only development metrics, even when test results are available."""
    if not configurations:
        raise ValueError("No configurations available for selection.")

    def selection_key(configuration: dict[str, Any]) -> tuple:
        summary = configuration["development"]["summary"]
        recall, hit, context = (summary[field] for field in (
            "recall_at_5", "hit_at_5", "mean_top5_context_tokens"
        ))
        if any(not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in (recall, hit, context)):
            raise ValueError("Selection requires finite development metrics.")
        if not 0 <= recall <= 1 or not 0 <= hit <= 1 or context < 0:
            raise ValueError("Invalid development metric range.")
        return (-recall, -hit, context,
                configuration["profile"] != "384", configuration["retrieval"] != "hybrid")

    selected = min(configurations, key=selection_key)
    return {
        "profile": selected["profile"],
        "retrieval": selected["retrieval"],
        "selection_split": "development",
        "method": SELECTION_METHOD,
        "development_metrics": selected["development"]["summary"],
    }


def write_csv(report: dict[str, Any], destination: Path) -> None:
    fields = ["profile", "retrieval", "split", "id", "category", "question",
              "expected_behavior", "hit_at_5", "recall_at_5", "top5_context_tokens",
              "retrieval_seconds", "retrieved_ids"]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for configuration in report["configurations"]:
            for split in ("development", "test"):
                for row in configuration[split]["rows"]:
                    csv_row = {field: row.get(field, "") for field in fields}
                    csv_row.update({
                        "profile": configuration["profile"],
                        "retrieval": configuration["retrieval"], "split": split,
                        "retrieved_ids": ";".join(str(hit["id"]) for hit in row["retrieved"]),
                    })
                    writer.writerow(csv_row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, default=ROOT / "evaluation" / "calibration.json")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation" / "questions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results" / "p1_retrieval_comparison.json")
    args = parser.parse_args()
    if args.output.resolve() in {
        (ROOT / "evaluation" / "results" / "dense_evaluation.json").resolve(),
        (ROOT / "evaluation" / "results" / "calibration.json").resolve(),
    }:
        raise ValueError("Comparison output must not overwrite the frozen P0 artifacts.")

    development = load_questions(args.development)
    final_test = load_questions(args.questions)
    check_separate_sets(development, final_test)
    development_hash, question_hash = file_sha256(args.development), file_sha256(args.questions)

    # One process, one shared model cold start. Each local retrieval pipeline gets
    # its own initialization query before timings used in the comparison.
    cold_started = time.perf_counter()
    from app.profiles import settings_for_profile
    from app.retrieval import retrieve_documents, retrieve_hybrid

    shared_settings = settings_for_profile(profile="384", retrieval="dense", gate="p1")
    retrieve_documents("workplace policy", shared_settings)
    shared_cold_seconds = time.perf_counter() - cold_started
    configurations = []
    for profile, mode in CONFIGURATIONS:
        settings = settings_for_profile(profile=profile, retrieval=mode, gate="p1")
        retriever = retrieve_documents if mode == "dense" else retrieve_hybrid
        started = time.perf_counter()
        retriever("workplace policy", settings)
        initialization_seconds = time.perf_counter() - started
        configuration = {
            "profile": profile, "retrieval": mode,
            "chunk_tokens": settings.chunk_tokens, "overlap_tokens": settings.overlap_tokens,
            "collection_name": settings.collection_name, "embedding_model": settings.embedding_model,
            "chunks_sha256": file_sha256(settings.chunks_path),
            "pipeline_initialization_seconds": round(initialization_seconds, 6),
            "development": evaluate_split(development, retriever, settings),
            "test": evaluate_split(final_test, retriever, settings),
        }
        configurations.append(configuration)
        print(json.dumps({"profile": profile, "retrieval": mode,
                          "development": configuration["development"]["summary"],
                          "test_diagnostic": configuration["test"]["summary"]}), flush=True)

    if file_sha256(args.development) != development_hash or file_sha256(args.questions) != question_hash:
        raise RuntimeError("Question files changed during comparison; refusing a mixed report.")
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "generation_evaluated": False, "api_calls": 0,
        "development_sha256": development_hash, "questions_sha256": question_hash,
        "shared_model_cold_start_seconds": round(shared_cold_seconds, 6),
        "timing_method": (
            "One process; shared BGE model/index first load timed once. Each configuration "
            "has a separate untimed-for-metrics initialization query. Reported query median/max "
            "are warm local retrieval only; generation, evidence gating and API latency are excluded."
        ),
        "metric_definition": (
            "Hit@5 and mean passage Recall@5 use gold text spans in the top five retrieved "
            "chunks from the labelled document, normalizing case and whitespace. Only answerable "
            "queries enter metric/context-token averages. Unsupported queries have no retrieval "
            "recall and this experiment does not test fallback behavior."
        ),
        "test_set_limitation": (
            "The final 15 questions were previously inspected for P0 failure analysis. "
            "P1 test results are diagnostic follow-up measurements, not a new held-out estimate."
        ),
        "configurations": configurations,
        "selected": choose_configuration(configurations),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(report, args.output.with_suffix(".csv"))
    print(json.dumps({"report": str(args.output), "selected": report["selected"]}, indent=2))


if __name__ == "__main__":
    main()
