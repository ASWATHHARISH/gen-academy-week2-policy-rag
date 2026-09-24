import hashlib
import json

import pytest

from app.config import Settings
from app.profiles import settings_for_profile
from ingestion.ingest import saved_documents


def test_profiles_isolate_chunks_collection_calibration_and_preserve_settings(monkeypatch):
    base = Settings(_env_file=None)
    original = base.model_dump()
    monkeypatch.setattr("app.profiles.get_settings", lambda: base)
    baseline = settings_for_profile("384", "dense", "p0")
    improved = settings_for_profile("384", "hybrid", "p1")
    small = settings_for_profile("256", "hybrid", "p1")
    assert baseline.chunks_path == improved.chunks_path
    assert baseline.calibration_path.name == "calibration.json"
    assert improved.calibration_path.name == "calibration_p1_384.json"
    assert small.calibration_path.name == "calibration_p1_256.json"
    assert small.chunks_path.parent.name == "chunks256"
    assert small.chunks_path != baseline.chunks_path
    assert small.collection_name != baseline.collection_name
    assert small.chunk_tokens == 256 and small.overlap_tokens == 48
    assert baseline.chunk_tokens == 384 and baseline.overlap_tokens == 64
    assert small.embedding_dir == baseline.embedding_dir == base.embedding_dir
    assert small.chroma_dir == baseline.chroma_dir == base.chroma_dir
    assert base.model_dump() == original


@pytest.mark.parametrize("args", [("999", "hybrid", "p1"), ("384", "unknown", "p1"), ("384", "dense", "unknown")])
def test_invalid_profiles_fail_explicitly(args):
    with pytest.raises(ValueError):
        settings_for_profile(*args)


def test_saved_snapshot_reuse_is_read_only_and_detects_changed_raw_content(tmp_path):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    raw.mkdir()
    processed.mkdir()
    source = {"id": "fixture", "url": "https://example.test/policy/"}
    body = b"<article>Original policy snapshot</article>"
    record = {"sha256": hashlib.sha256(body).hexdigest(), "source_url": source["url"], "snapshot_date": "2026-09-23"}
    document = {**record, "document_id": "fixture", "sections": [{"text": "Original policy snapshot"}]}
    (raw / "fixture.html").write_bytes(body)
    (raw / "fixture.snapshot.json").write_text(json.dumps(record), encoding="utf-8")
    path = processed / "fixture.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    original = path.read_bytes()
    assert saved_documents({"sources": [source]}, raw, processed) == [document]
    assert path.read_bytes() == original
    (raw / "fixture.html").write_bytes(b"Changed source")
    with pytest.raises(ValueError, match="snapshot mismatch"):
        saved_documents({"sources": [source]}, raw, processed)


def test_missing_snapshot_does_not_trigger_a_download(tmp_path):
    with pytest.raises(FileNotFoundError, match="existing approved snapshots"):
        saved_documents({"sources": [{"id": "missing", "url": "https://example.test/"}]}, tmp_path, tmp_path)
