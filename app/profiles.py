"""Explicit retrieval profiles that keep the frozen baseline artifacts intact."""
from app.config import ROOT, Settings, get_settings


def settings_for_profile(profile: str = "384", retrieval: str = "hybrid",
                         gate: str = "p1") -> Settings:
    if profile not in {"384", "256"}:
        raise ValueError("Unknown chunk profile; choose 384 or 256.")
    if retrieval not in {"dense", "hybrid"}:
        raise ValueError("Unknown retrieval mode; choose dense or hybrid.")
    if gate not in {"p0", "p1"}:
        raise ValueError("Unknown evidence gate; choose p0 or p1.")
    processed = ROOT / "data" / "processed"
    chunks_path = processed / "chunks.jsonl" if profile == "384" else processed / "chunks256" / "chunks.jsonl"
    calibration_name = "calibration.json" if gate == "p0" else f"calibration_p1_{profile}.json"
    return get_settings().model_copy(update={
        "chunk_tokens": int(profile),
        "overlap_tokens": 64 if profile == "384" else 48,
        "collection_name": f"gitlab_policy_bge_{profile}",
        "chunks_path": chunks_path,
        "calibration_path": ROOT / "evaluation" / "results" / calibration_name,
        "retrieval_mode": retrieval,
        "gate_mode": gate,
    })
