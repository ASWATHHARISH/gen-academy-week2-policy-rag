"""Local dense or BM25+dense retrieval from a verified policy snapshot."""
from functools import lru_cache
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.bm25 import BM25Index, reciprocal_rank_fusion


class RetrievalError(RuntimeError):
    pass


def index_fingerprint(settings: Settings) -> str:
    digest = hashlib.sha256()
    with settings.chunks_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_index_manifest(settings: Settings) -> dict[str, Any]:
    """A completed index must match its source file, embedding revision and config."""
    path = settings.chunks_path.parent / "index_manifest.json"
    if not path.is_file():
        raise RetrievalError("index_incomplete")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        model = json.loads((settings.embedding_dir / "download-manifest.json").read_text(encoding="utf-8"))
        if (
            manifest.get("collection_name") != settings.collection_name
            or manifest.get("model") != settings.embedding_model
            or model.get("model") != settings.embedding_model
            or manifest.get("revision") != model.get("revision")
            or manifest.get("chunk_tokens") != settings.chunk_tokens
            or manifest.get("overlap_tokens") != settings.overlap_tokens
            or manifest.get("index_sha256") != index_fingerprint(settings)
        ):
            raise RetrievalError("index_configuration_mismatch")
        payload = {key: manifest[key] for key in (
            "documents", "model", "revision", "chunk_tokens", "overlap_tokens", "extractor_version"
        )}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        if fingerprint != manifest.get("corpus_fingerprint"):
            raise RetrievalError("index_fingerprint_mismatch")
        return manifest
    except RetrievalError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise RetrievalError("index_manifest_invalid") from None


def effective_threshold(settings: Settings) -> float:
    """Only apply calibration produced for this exact corpus and model/index."""
    default = float(settings.evidence_threshold)
    if not math.isfinite(default) or not -1 <= default <= 1.000001:
        raise RetrievalError("invalid_evidence_threshold")
    if not settings.calibration_path.is_file():
        return default
    try:
        data = json.loads(settings.calibration_path.read_text(encoding="utf-8"))
        if (
            data.get("embedding_model") != settings.embedding_model
            or data.get("collection_name") != settings.collection_name
            or data.get("index_sha256") != index_fingerprint(settings)
            or data.get("retrieval_mode", "dense") != getattr(settings, "retrieval_mode", "dense")
            or data.get("gate_mode", "p0") != getattr(settings, "gate_mode", "p0")
        ):
            return default
        threshold = float(data["threshold"])
        # A value just above one intentionally rejects even a perfect cosine
        # match when development calibration selects an abstain-all setting.
        return threshold if math.isfinite(threshold) and -1 <= threshold <= 1.000001 else default
    except (OSError, ValueError, TypeError, KeyError):
        return default


def _tokens(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.casefold())
    return set(zip(*(words[i:] for i in range(5)))) if len(words) >= 5 else {(w,) for w in words}


def deduplicate_evidence(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Remove exact text and heavily overlapping same-document passages."""
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    signatures: list[tuple[str, set[tuple[str, ...]]]] = []
    for item in items:
        text_key = " ".join(item["text"].split()).casefold()
        if not text_key or item["id"] in seen_ids or text_key in seen_texts:
            continue
        doc_id = str(item.get("metadata", {}).get("document_id", ""))
        sig = _tokens(item["text"])
        if any(
            doc_id and doc_id == prev_doc and sig and prev_sig
            and len(sig & prev_sig) / min(len(sig), len(prev_sig)) >= 0.8
            for prev_doc, prev_sig in signatures
        ):
            continue
        selected.append(item)
        seen_ids.add(item["id"])
        seen_texts.add(text_key)
        signatures.append((doc_id, sig))
        if len(selected) >= limit:
            break
    return selected


def _dense_query(query: str, settings: Settings, limit: int | None = None):
    """Share one index validation, Chroma query and query embedding per retrieval."""
    if not settings.chroma_dir.is_dir() or not settings.chunks_path.is_file():
        raise RetrievalError("index_missing")
    manifest = validate_index_manifest(settings)
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from app.embeddings import get_embeddings

    try:
        client = chromadb.PersistentClient(
            path=str(settings.chroma_dir), settings=ChromaSettings(anonymized_telemetry=False)
        )
        # get_collection must never silently create an empty or default-model index.
        collection = client.get_collection(settings.collection_name, embedding_function=None)
        metadata = collection.metadata or {}
        if (metadata.get("hnsw:space") != "cosine"
                or metadata.get("corpus_fingerprint") != manifest["corpus_fingerprint"]
                or metadata.get("embedding_model") != settings.embedding_model
                or metadata.get("model_revision") != manifest["revision"]):
            raise RetrievalError("collection_configuration_mismatch")
        count = collection.count()
        if count != manifest.get("chunk_count"):
            raise RetrievalError("index_count_mismatch")
        if not count:
            return [], collection, [], manifest
        query_vector = get_embeddings(settings).embed_query(query)
        result = collection.query(
            query_embeddings=[query_vector], n_results=min(limit or settings.retrieval_k, count),
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict[str, Any]] = []
        for cid, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            distance = float(distance)
            if not math.isfinite(distance) or not -1e-6 <= distance <= 2 + 1e-6:
                raise RetrievalError("invalid_cosine_distance")
            # Cosine distance = 1 - cosine similarity. Only clamp floating-point noise.
            score = min(1.0, max(-1.0, 1.0 - distance))
            if isinstance(text, str) and text.strip():
                hits.append({"id": cid, "text": text, "metadata": metadata or {}, "score": score})
        return hits, collection, query_vector, manifest
    except RetrievalError:
        raise
    except Exception:
        raise RetrievalError("retrieval_unavailable") from None


def retrieve_documents(query: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Dense-only public API retained unchanged for baseline evaluation."""
    settings = settings or get_settings()
    hits, _, _, _ = _dense_query(query, settings)
    return hits


@lru_cache(maxsize=2)
def _load_bm25(chunks_path: str, fingerprint: str) -> BM25Index:
    """Changing any corpus byte creates a new sparse index cache entry."""
    content = Path(chunks_path).read_bytes()
    if hashlib.sha256(content).hexdigest() != fingerprint:
        raise RetrievalError("sparse_snapshot_changed")
    documents = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
    return BM25Index(documents, k1=1.5, b=0.75)


def _cosine_similarity(query_vector, document_vector) -> float:
    if len(query_vector) != len(document_vector) or not len(query_vector):
        raise RetrievalError("sparse_embedding_dimension_mismatch")
    if not all(math.isfinite(float(value)) for value in (*query_vector, *document_vector)):
        raise RetrievalError("invalid_sparse_embedding")
    qnorm = math.sqrt(math.fsum(float(value) ** 2 for value in query_vector))
    dnorm = math.sqrt(math.fsum(float(value) ** 2 for value in document_vector))
    if not qnorm or not dnorm:
        raise RetrievalError("invalid_sparse_embedding")
    cosine = math.fsum(float(q) * float(d) for q, d in zip(query_vector, document_vector)) / (qnorm * dnorm)
    return min(1.0, max(-1.0, cosine))


def retrieve_hybrid(query: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Equal-weight RRF of dense10 and BM25 top10; score always means cosine.

    RRF establishes order only. Sparse-only hits receive a real cosine score
    from their stored vectors, keeping evidence threshold semantics unchanged.
    """
    settings = settings or get_settings()
    dense, collection, query_vector, manifest = _dense_query(query, settings, limit=10)
    if len(query_vector) == 0:
        return []
    try:
        sparse_index = _load_bm25(str(settings.chunks_path.resolve()), manifest["index_sha256"])
        bm25_scores = sparse_index.scores(query)
        sparse = sparse_index.ranked(bm25_scores, limit=10)
        dense_by_id = {item["id"]: item for item in dense}
        candidates = {item["id"]: dict(item) for item in [*sparse, *dense]}
        sparse_only = [item["id"] for item in sparse if item["id"] not in dense_by_id]
        if sparse_only:
            stored = collection.get(ids=sparse_only, include=["embeddings"])
            vectors = stored.get("embeddings")
            if vectors is None or set(stored["ids"]) != set(sparse_only):
                raise RetrievalError("sparse_embedding_missing")
            for cid, vector in zip(stored["ids"], vectors):
                candidates[cid]["score"] = _cosine_similarity(query_vector, vector)
        ranking = reciprocal_rank_fusion([item["id"] for item in dense], [item["id"] for item in sparse], k=60)
        output = []
        for ranks in ranking[:10]:
            cid = ranks["id"]
            item = candidates[cid]
            output.append({**item, **ranks, "dense_score": item["score"],
                           "bm25_score": bm25_scores.get(cid, 0.0)})
        return output
    except RetrievalError:
        raise
    except Exception:
        raise RetrievalError("hybrid_retrieval_unavailable") from None


def retrieve(query: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Dispatch the selected profile while keeping dense evaluation explicit."""
    settings = settings or get_settings()
    mode = getattr(settings, "retrieval_mode", "dense")
    if mode == "dense":
        return retrieve_documents(query, settings)
    if mode == "hybrid":
        return retrieve_hybrid(query, settings)
    raise RetrievalError("invalid_retrieval_mode")
