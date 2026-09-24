"""Cloud setup tests use tiny fixtures and fake models; never contact a service."""
import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from app import cloud_bootstrap as cloud


def frozen_fixture(tmp_path):
    chunks_path = tmp_path / "chunks256" / "chunks.jsonl"
    chunks_path.parent.mkdir()
    rows = [{"id": "chunk-1", "text": "The policy requires approved access.",
             "metadata": {"document_id": "security", "title": "Security policy"}}]
    data = (json.dumps(rows[0]) + "\n").encode()
    chunks_path.write_bytes(data)
    payload = {"documents": [["security", "snapshot-hash"]], "model": cloud.APPROVED_MODEL,
               "revision": cloud.APPROVED_REVISION, "chunk_tokens": 256,
               "overlap_tokens": 48, "extractor_version": 1}
    manifest = {**payload, "collection_name": "gitlab_policy_bge_256", "chunk_count": 1,
                "corpus_fingerprint": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                "index_sha256": hashlib.sha256(data).hexdigest()}
    (chunks_path.parent / "index_manifest.json").write_text(json.dumps(manifest))
    settings = SimpleNamespace(chunks_path=chunks_path, embedding_model=cloud.APPROVED_MODEL,
                               chunk_tokens=256, overlap_tokens=48, collection_name="gitlab_policy_bge_256",
                               embedding_dir=tmp_path / "model", chroma_dir=tmp_path / "chroma",
                               api_budget_path=tmp_path / "api_budget.json")
    return settings, manifest, rows


def test_frozen_snapshot_hash_and_profile_verified(tmp_path):
    settings, manifest, rows = frozen_fixture(tmp_path)
    assert cloud._snapshot(settings) == (manifest, rows)
    settings.chunks_path.write_bytes(settings.chunks_path.read_bytes() + b"\n")
    with pytest.raises(cloud.CloudSetupError, match="cloud_snapshot_invalid"):
        cloud._snapshot(settings)


def test_wrong_profile_fails_before_download(tmp_path, monkeypatch):
    settings, _, _ = frozen_fixture(tmp_path)
    settings.chunk_tokens = 384
    monkeypatch.setattr(cloud, "_ensure_model", lambda *args: pytest.fail("Unexpected download"))
    with pytest.raises(cloud.CloudSetupError, match="cloud_profile_not_approved"):
        cloud.ensure_cloud_assets(settings, allow_download=True)


def test_missing_model_does_not_download_without_explicit_opt_in(tmp_path):
    settings, _, _ = frozen_fixture(tmp_path)
    with pytest.raises(cloud.CloudSetupError, match="cloud_model_missing_download_not_allowed"):
        cloud.ensure_cloud_assets(settings)
    assert not settings.api_budget_path.exists()


def test_setup_never_initializes_or_resets_api_budget(tmp_path, monkeypatch):
    settings, _, _ = frozen_fixture(tmp_path)
    settings.api_budget_path.write_text('{"attempts":23}')
    monkeypatch.setattr(cloud, "_ensure_model", lambda *args: None)
    monkeypatch.setattr(cloud, "validate_index_manifest", lambda *args: None)
    monkeypatch.setattr(cloud, "_ensure_index", lambda *args: None)
    assert cloud.ensure_cloud_assets(settings)["chunk_count"] == 1
    assert settings.api_budget_path.read_text() == '{"attempts":23}'


def test_model_manifest_cannot_escape_model_directory(tmp_path):
    target = tmp_path / "model"
    target.mkdir()
    record = {"model": cloud.APPROVED_MODEL, "revision": cloud.APPROVED_REVISION,
              "files": [{"path": "../outside", "sha256": "unused"},
                        {"path": "model.safetensors", "sha256": "unused"},
                        {"path": "tokenizer.json", "sha256": "unused"}]}
    (target / "download-manifest.json").write_text(json.dumps(record))
    with pytest.raises(cloud.CloudSetupError, match="cloud_model_manifest_invalid"):
        cloud._model_is_ready(target)


def test_index_resume_reuses_known_ids_and_preserves_metadata(tmp_path, monkeypatch):
    settings, manifest, rows = frozen_fixture(tmp_path)
    stored = {}
    class Collection:
        metadata = None
        def get(self, include):
            return {"ids": list(stored)}
        def upsert(self, ids, documents, metadatas, embeddings):
            for index, cid in enumerate(ids):
                stored[cid] = (documents[index], metadatas[index], embeddings[index])
        def count(self):
            return len(stored)
    collection = Collection()
    class Client:
        def get_or_create_collection(self, name, metadata, embedding_function):
            collection.metadata = collection.metadata or metadata
            return collection
    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace(PersistentClient=lambda **kwargs: Client()))
    monkeypatch.setitem(sys.modules, "chromadb.config", SimpleNamespace(Settings=lambda **kwargs: None))
    monkeypatch.setitem(sys.modules, "app.embeddings", SimpleNamespace(get_embeddings=lambda settings:
                        SimpleNamespace(embed_documents=lambda texts: [[1.0, 0.0] for text in texts])))
    cloud._ensure_index(settings, manifest, rows)
    cloud._ensure_index(settings, manifest, rows)
    assert len(stored) == 1
    assert stored["chunk-1"] == (rows[0]["text"], rows[0]["metadata"], [1.0, 0.0])
    stored["foreign-chunk"] = ("Foreign", {}, [1.0, 0.0])
    with pytest.raises(cloud.CloudSetupError, match="cloud_existing_index_unknown_chunks"):
        cloud._ensure_index(settings, manifest, rows)


def test_bootstrap_suppresses_raw_dependency_error(tmp_path, monkeypatch):
    settings, _, _ = frozen_fixture(tmp_path)
    def broken(*args):
        raise RuntimeError("private provider detail must not be displayed")
    monkeypatch.setattr(cloud, "_ensure_model", broken)
    with pytest.raises(cloud.CloudSetupError) as error:
        cloud.ensure_cloud_assets(settings, allow_download=True)
    assert str(error.value) == "cloud_bootstrap_failed"
