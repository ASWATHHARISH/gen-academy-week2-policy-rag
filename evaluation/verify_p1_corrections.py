"""Record targeted zero-API regression checks without overwriting live results."""
from datetime import datetime, timezone
import json

from app.config import ROOT
from app.graph import run_query
from app.profiles import settings_for_profile


def main():
    settings = settings_for_profile("256", retrieval="hybrid", gate="p1")
    baseline_path = ROOT / "evaluation" / "results" / "p1_hybrid_256_evaluation.json"
    live = json.loads(baseline_path.read_text(encoding="utf-8"))
    original = next(row for row in live["rows"] if row["id"] == "B1")
    before = json.loads(settings.api_budget_path.read_text(encoding="utf-8"))["attempts"]
    def forbidden(*args):
        raise AssertionError("Targeted scope checks must not retrieve or generate")
    queries = [original["question"], "What are my statutory annual leave entitlements in France?",
               "What minimum leave does the law guarantee employees?",
               "Are we legally entitled to severance pay?"]
    results = [run_query(query, settings, retriever=forbidden, generator=forbidden) for query in queries]
    assert all(row["status"] == "fallback" and row["reason"] == "personal_legal_entitlement_out_of_scope"
               and row["api_called"] is False for row in results)
    after = json.loads(settings.api_budget_path.read_text(encoding="utf-8"))["attempts"]
    assert before == after
    checks = [{"id": row["id"], "passing_cosine_in_actual_evidence":
               any(item["score"] >= row["response"]["threshold"] for item in row["response"]["evidence"])}
              for row in live["rows"] if row["response"]["status"] == "answered"]
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "method": "Targeted production LangGraph with forbidden retrieval/generation callbacks; no API. Not a second full live evaluation.",
              "baseline_result_preserved": str(baseline_path.relative_to(ROOT)),
              "original_B1_status": original["response"]["status"],
              "api_attempts_before": before, "api_attempts_after": after,
              "targeted_scope_results": results, "original_answered_evidence_gate_audit": checks,
              "limitation": "A narrow deterministic legal-entitlement boundary is not a general semantic or jurisdiction checker."}
    output = ROOT / "evaluation" / "results" / "p1_corrections_verification.json"
    if output.exists():
        raise FileExistsError("Preserving existing targeted verification")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"targeted_scope_checks_passed": len(results), "additional_api_attempts": after-before,
                      "all_prior_answers_had_passing_selected_evidence": all(row["passing_cosine_in_actual_evidence"] for row in checks)}, indent=2))


if __name__ == "__main__":
    main()
