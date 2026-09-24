"""Read actual saved evaluation records without model, index, or API dependencies."""
from copy import deepcopy
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "evaluation" / "results" / "p1_hybrid_256_evaluation.json"
DEMO_IDS = ("N1", "U1", "F1")


def demo_only_enabled() -> bool:
    return os.environ.get("RAG_DEMO_ONLY", "").strip().lower() in {"1", "true", "yes"}


def load_saved_demo(path: Path = DEFAULT_RESULTS) -> dict:
    """Return unmodified real responses, with explicit replay provenance."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise ValueError("Saved evaluation format is invalid.")
    by_id = {row.get("id"): row for row in data["rows"] if isinstance(row, dict)}
    examples = []
    for question_id in DEMO_IDS:
        row = by_id.get(question_id)
        if not isinstance(row, dict) or not isinstance(row.get("question"), str):
            raise ValueError("A required saved demo question is missing.")
        response = row.get("response")
        if (not isinstance(response, dict) or response.get("status") not in {"answered", "fallback", "error"}
                or not isinstance(response.get("answer"), str)
                or not isinstance(response.get("citations"), list)
                or not isinstance(response.get("evidence"), list)):
            raise ValueError("A saved demo response is invalid.")
        examples.append({"id": question_id, "question": row["question"],
                         "response": deepcopy(response)})
    return {"timestamp_utc": data.get("timestamp_utc", ""),
            "model": data.get("model", "Gemini"), "system": data.get("system", "hybrid"),
            "chunk_tokens": data.get("chunk_tokens", 256),
            "overlap_tokens": data.get("overlap_tokens", 48),
            "source_file": DEFAULT_RESULTS.name if Path(path) == DEFAULT_RESULTS else Path(path).name,
            "examples": examples}
