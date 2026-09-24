"""CPU BGE embeddings loaded only from the explicitly downloaded local model."""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from app.config import Settings, get_settings

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=2)
def _load_embeddings(model_path: str):
    path = Path(model_path)
    if not (path / "model.safetensors").is_file() or not (path / "tokenizer.json").is_file():
        raise FileNotFoundError("Local BGE model is missing. Run: python -m ingestion.download_model")
    import torch
    from langchain_huggingface import HuggingFaceEmbeddings

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    return HuggingFaceEmbeddings(
        model_name=str(path),
        model_kwargs={"device": "cpu", "local_files_only": True, "trust_remote_code": False},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 16},
        query_encode_kwargs={"normalize_embeddings": True, "prompt": QUERY_INSTRUCTION,
                             "batch_size": 16},
        show_progress=False,
    )


def get_embeddings(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.embedding_model != "BAAI/bge-small-en-v1.5":
        raise ValueError("P0 supports only the approved BGE small embedding model.")
    return _load_embeddings(str(settings.embedding_dir.resolve()))
