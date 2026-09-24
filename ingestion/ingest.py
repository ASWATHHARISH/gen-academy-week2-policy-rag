"""Fetch the approved corpus, preserve source sections, and build a local Chroma index."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from app.config import ROOT
from app.embeddings import get_embeddings
from app.profiles import settings_for_profile
from ingestion.chunking import chunk_document
from ingestion.loaders import MANIFEST_PATH, download_sources, load_manifest


def saved_documents(manifest: dict, raw_dir: Path, processed_dir: Path) -> list[dict]:
    """Validate and reuse exactly the frozen twelve snapshots without rewriting them."""
    documents = []
    for source in manifest["sources"]:
        raw_path = raw_dir / f"{source['id']}.html"
        record_path = raw_dir / f"{source['id']}.snapshot.json"
        document_path = processed_dir / f"{source['id']}.json"
        if not all(path.is_file() for path in (raw_path, record_path, document_path)):
            raise FileNotFoundError("The 256 profile requires the existing approved snapshots; build the 384 profile first.")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        document = json.loads(document_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if (record.get("sha256") != digest or document.get("sha256") != digest
                or record.get("source_url") != source["url"] or document.get("source_url") != source["url"]
                or document.get("document_id") != source["id"]
                or document.get("snapshot_date") != record.get("snapshot_date")
                or not document.get("sections")):
            raise ValueError(f"Frozen source snapshot mismatch: {source['id']}")
        documents.append(document)
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--profile", choices=["384", "256"], default="384")
    parser.add_argument("--chunk-tokens", type=int, default=None)
    parser.add_argument("--overlap-tokens", type=int, default=None)
    parser.add_argument("--extract-only", action="store_true", help="Fetch and clean; no embedding model or index needed.")
    args = parser.parse_args()
    settings = settings_for_profile(args.profile)
    if ((args.chunk_tokens is not None and args.chunk_tokens != settings.chunk_tokens)
            or (args.overlap_tokens is not None and args.overlap_tokens != settings.overlap_tokens)):
        raise ValueError("Explicit chunk settings must match the selected --profile: 384/64 or 256/48.")
    manifest = load_manifest(args.sources)
    processed = ROOT / "data" / "processed"
    if args.profile == "256":
        documents = saved_documents(manifest, ROOT / "data" / "raw", processed)
    else:
        documents = download_sources(manifest, ROOT / "data" / "raw", processed)
    corpus_manifest = {
        "corpus_name": manifest["corpus_name"], "publisher": manifest["publisher"],
        "license": manifest["license"], "license_url": manifest["license_url"],
        "attribution_url": manifest["attribution_url"], "modifications": manifest["modifications"],
        "documents": [{key: document[key] for key in ("document_id", "title", "source_url", "sha256", "snapshot_date")}
                      for document in documents],
    }
    if args.profile == "384":
        (processed / "corpus_manifest.json").write_text(json.dumps(corpus_manifest, indent=2), encoding="utf-8")
    if args.extract_only:
        print(f"Extracted all {len(documents)} approved documents; indexing not requested.")
        return
    model_manifest_path = settings.embedding_dir / "download-manifest.json"
    if not model_manifest_path.exists():
        raise FileNotFoundError("Download the approved local model before indexing: python -m ingestion.download_model")
    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(settings.embedding_dir), local_files_only=True,
                                              trust_remote_code=False, use_fast=True)
    chunks = [chunk for document in documents for chunk in chunk_document(
        document, tokenizer, settings.chunk_tokens, settings.overlap_tokens)]
    if not chunks:
        raise ValueError("No chunks extracted; refusing empty index.")
    fingerprint_payload = {"documents": sorted((d["document_id"], d["sha256"]) for d in documents),
                           "model": settings.embedding_model, "revision": model_manifest["revision"],
                           "chunk_tokens": settings.chunk_tokens, "overlap_tokens": settings.overlap_tokens,
                           "extractor_version": 1}
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()).hexdigest()
    from chromadb import PersistentClient
    from chromadb.config import Settings as ChromaSettings
    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    client = PersistentClient(path=str(settings.chroma_dir), settings=ChromaSettings(anonymized_telemetry=False))
    collection_names = {getattr(collection, "name", collection) for collection in client.list_collections()}
    if settings.collection_name in collection_names:
        existing = client.get_collection(settings.collection_name, embedding_function=None)
        if (existing.metadata or {}).get("corpus_fingerprint") != fingerprint:
            raise ValueError("Existing Chroma collection uses a different snapshot/model/chunk configuration. "
                             "Choose a new COLLECTION_NAME; old data will not be deleted or mixed.")
    collection_metadata = {"hnsw:space": "cosine", "corpus_fingerprint": fingerprint,
                           "embedding_model": settings.embedding_model, "model_revision": model_manifest["revision"],
                           "chunk_tokens": settings.chunk_tokens, "overlap_tokens": settings.overlap_tokens}
    vectorstore = Chroma(client=client, collection_name=settings.collection_name,
                         embedding_function=get_embeddings(settings), collection_metadata=collection_metadata)
    for offset in range(0, len(chunks), 64):
        batch = chunks[offset:offset + 64]
        vectorstore.add_documents([Document(page_content=item["text"], metadata=item["metadata"]) for item in batch],
                                  ids=[item["id"] for item in batch])
        print(f"Indexed {min(offset + 64, len(chunks))}/{len(chunks)} chunks", flush=True)
    count = client.get_collection(settings.collection_name, embedding_function=None).count()
    if count != len(chunks):
        raise ValueError(f"Unexpected collection size {count}; expected {len(chunks)}. Inspect before serving.")
    settings.chunks_path.parent.mkdir(parents=True, exist_ok=True)
    settings.chunks_path.write_text("".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks), encoding="utf-8")
    index_manifest = {**fingerprint_payload, "corpus_fingerprint": fingerprint,
                      "collection_name": settings.collection_name, "chunk_count": count,
                      "index_sha256": hashlib.sha256(settings.chunks_path.read_bytes()).hexdigest(),
                      "document_count": len(documents), "indexed_at": datetime.now(timezone.utc).isoformat()}
    (settings.chunks_path.parent / "index_manifest.json").write_text(json.dumps(index_manifest, indent=2), encoding="utf-8")
    print(f"Complete: {len(documents)} documents, {count} chunks; local collection {settings.collection_name}.")


if __name__ == "__main__":
    main()
