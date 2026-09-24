"""Opt-in cloud setup from the frozen corpus; never called in saved-demo mode.

No Gemini calls, handbook refetches, or API-budget writes are made here. A new
host may download only the already approved BGE revision, then rebuild Chroma.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from app.budget import _locked
from app.config import Settings
from app.retrieval import validate_index_manifest
from ingestion.download_model import APPROVED_MODEL, APPROVED_REVISION, ALLOW_PATTERNS


class CloudSetupError(RuntimeError):
    """Only fixed, non-secret status codes are exposed to the cloud interface."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot(settings: Settings):
    """Check the committed snapshot before any download or index mutation."""
    if (settings.embedding_model != APPROVED_MODEL or settings.chunk_tokens != 256
            or settings.overlap_tokens != 48 or settings.collection_name != "gitlab_policy_bge_256"):
        raise CloudSetupError("cloud_profile_not_approved")
    try:
        data = settings.chunks_path.read_bytes()
        manifest = json.loads((settings.chunks_path.parent / "index_manifest.json").read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        payload = {key: manifest[key] for key in (
            "documents", "model", "revision", "chunk_tokens", "overlap_tokens", "extractor_version")}
        expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        if (manifest["model"] != APPROVED_MODEL or manifest["revision"] != APPROVED_REVISION
                or manifest["collection_name"] != settings.collection_name
                or manifest["chunk_tokens"] != 256 or manifest["overlap_tokens"] != 48
                or manifest["index_sha256"] != hashlib.sha256(data).hexdigest()
                or manifest["corpus_fingerprint"] != expected
                or manifest["chunk_count"] != len(rows) or not rows
                or len({row["id"] for row in rows}) != len(rows)
                or any(not isinstance(row["text"], str) or not row["text"].strip()
                       or not isinstance(row["metadata"], dict) for row in rows)):
            raise CloudSetupError("cloud_snapshot_invalid")
        return manifest, rows
    except CloudSetupError:
        raise
    except Exception:
        raise CloudSetupError("cloud_snapshot_missing_or_invalid") from None


def _model_is_ready(target: Path) -> bool:
    try:
        manifest = json.loads((target / "download-manifest.json").read_text(encoding="utf-8"))
        if manifest.get("model") != APPROVED_MODEL or manifest.get("revision") != APPROVED_REVISION:
            raise CloudSetupError("cloud_model_revision_mismatch")
        files = manifest.get("files", [])
        names = {item["path"] for item in files}
        if not {"model.safetensors", "tokenizer.json"}.issubset(names):
            return False
        for item in files:
            relative = Path(item["path"])
            path = (target / relative).resolve()
            if relative.is_absolute() or not path.is_relative_to(target.resolve()):
                raise CloudSetupError("cloud_model_manifest_invalid")
            if not path.is_file() or _sha256(path) != item["sha256"]:
                return False
        return True
    except FileNotFoundError:
        return False
    except CloudSetupError:
        raise
    except Exception:
        raise CloudSetupError("cloud_model_manifest_invalid") from None


def _ensure_model(settings: Settings, allow_download: bool):
    target = settings.embedding_dir
    if _model_is_ready(target):
        return
    if not allow_download:
        raise CloudSetupError("cloud_model_missing_download_not_allowed")
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=APPROVED_MODEL, revision=APPROVED_REVISION,
                      local_dir=str(target), allow_patterns=ALLOW_PATTERNS,
                      max_workers=2, token=False)
    if not (target / "model.safetensors").is_file() or not (target / "tokenizer.json").is_file():
        raise CloudSetupError("cloud_model_download_incomplete")
    files = [{"path": path.relative_to(target).as_posix(), "bytes": path.stat().st_size,
              "sha256": _sha256(path)} for path in sorted(target.rglob("*"))
             if path.is_file() and ".cache" not in path.relative_to(target).parts
             and path.name != "download-manifest.json"]
    record = {"model": APPROVED_MODEL, "revision": APPROVED_REVISION, "license": "MIT",
              "downloaded_at": datetime.now(timezone.utc).isoformat(), "files": files,
              "total_bytes": sum(item["bytes"] for item in files)}
    (target / "download-manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


def _ensure_index(settings: Settings, manifest: dict, rows: list[dict]):
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from app.embeddings import get_embeddings

    client = chromadb.PersistentClient(path=str(settings.chroma_dir),
                                       settings=ChromaSettings(anonymized_telemetry=False))
    metadata = {"hnsw:space": "cosine", "corpus_fingerprint": manifest["corpus_fingerprint"],
                "embedding_model": APPROVED_MODEL, "model_revision": APPROVED_REVISION,
                "chunk_tokens": 256, "overlap_tokens": 48}
    collection = client.get_or_create_collection(settings.collection_name, metadata=metadata,
                                                 embedding_function=None)
    if any((collection.metadata or {}).get(key) != value for key, value in metadata.items()):
        raise CloudSetupError("cloud_existing_index_mismatch")
    existing_ids = set(collection.get(include=[])["ids"])
    expected_ids = {row["id"] for row in rows}
    if not existing_ids.issubset(expected_ids):
        raise CloudSetupError("cloud_existing_index_unknown_chunks")
    missing = [row for row in rows if row["id"] not in existing_ids]
    if missing:
        embeddings = get_embeddings(settings)
        for offset in range(0, len(missing), 16):
            batch = missing[offset:offset + 16]
            texts = [row["text"] for row in batch]
            collection.upsert(ids=[row["id"] for row in batch], documents=texts,
                              metadatas=[row["metadata"] for row in batch],
                              embeddings=embeddings.embed_documents(texts))
    if collection.count() != len(rows):
        raise CloudSetupError("cloud_index_incomplete")


def ensure_cloud_assets(settings: Settings, *, allow_download: bool = False) -> dict:
    """Call only after a private live-mode authorization gate; cache per process.

    Partial matching indexes can resume. Foreign indexes are never deleted or
    overwritten. Rebuilding an index does not reset or create an API ledger.
    """
    try:
        manifest, rows = _snapshot(settings)
        with _locked(settings.chroma_dir.parent / ".cloud-bootstrap.lock"):
            _ensure_model(settings, allow_download)
            validate_index_manifest(settings)
            _ensure_index(settings, manifest, rows)
        return {"ready": True, "chunk_count": len(rows), "model": APPROVED_MODEL,
                "revision": APPROVED_REVISION}
    except CloudSetupError:
        raise
    except Exception:
        raise CloudSetupError("cloud_bootstrap_failed") from None
