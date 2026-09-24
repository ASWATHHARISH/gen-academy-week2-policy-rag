"""Explicit live UI check: two submissions; may use up to two Gemini attempts.

Not part of pytest. Uses Streamlit AppTest with the real graph and records any
service failure honestly. A rerender must not cause another graph/API request.
"""
import argparse
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-live", action="store_true", required=True)
    parser.add_argument("--p1", action="store_true", help="Check hybrid Workday answer and legal-scope fallback.")
    args = parser.parse_args()
    destination = ROOT / "evaluation" / "results" / ("p1_ui_smoke.json" if args.p1 else "ui_smoke.json")
    if destination.exists():
        raise FileExistsError("Preserve existing UI verification; choose a new run artifact.")
    from app.config import get_settings
    from streamlit.testing.v1 import AppTest

    settings = get_settings()
    def attempts():
        return json.loads(settings.api_budget_path.read_text(encoding="utf-8"))["attempts"]

    before = attempts()
    app = AppTest.from_file(str(ROOT / "ui" / "streamlit_app.py"), default_timeout=120).run()
    rows = []
    questions = [("N1", "What is the minimum password length under GitLab Password Standards?"),
                 ("U1", "How many paid days off does GitLab offer for adopting a pet?")]
    if args.p1:
        questions = [("F1", "Where must GitLab team members log their time away?"),
                     ("B1", "How many paid sick days am I legally entitled to?")]
    for qid, question in questions:
        app.text_area[0].set_value(question)
        app.button[0].click().run(timeout=120)
        if app.exception:
            rows.append({"id": qid, "status": "ui_exception"})
            continue
        result = dict(app.session_state["policy_result"])
        after_submit = attempts()
        app.run(timeout=120)
        stable = attempts() == after_submit
        row = {"id": qid, "question": question, "response": result,
               "rerender_added_no_api_attempt": stable,
               "ui_success": [entry.value for entry in app.success],
               "ui_info": [entry.value for entry in app.info],
               "ui_error": [entry.value for entry in app.error]}
        rows.append(row)
        print(json.dumps({"id": qid, "status": result["status"], "reason": result["reason"],
                          "rerender_added_no_api_attempt": stable}), flush=True)
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "method": "Real Streamlit AppTest with real graph, local retrieval and Gemini; not a browser screenshot.",
              "note": "Separate live UI verification; original 15-question evaluation unchanged.",
              "retrieval_mode": settings.retrieval_mode, "gate_mode": settings.gate_mode,
              "chunk_tokens": settings.chunk_tokens,
              "api_attempts_before": before, "api_attempts_after": attempts(), "rows": rows}
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {destination.name}; total API attempts: {attempts()}.")


if __name__ == "__main__":
    main()
