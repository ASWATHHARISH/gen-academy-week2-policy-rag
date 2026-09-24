import re

import pytest

from ingestion.chunking import chunk_document


class OffsetTokenizer:
    """Deterministic tokenizer fixture; no model download or network."""

    def encode(self, text, add_special_tokens=True):
        return list(range(len(re.findall(r"\S+", text)) + (2 if add_special_tokens else 0)))

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        return {"offset_mapping": [(match.start(), match.end()) for match in re.finditer(r"\S+", text)]}


def document():
    return {"document_id": "policy", "title": "Example Policy", "source_url": "https://example.test/policy/",
            "snapshot_date": "2026-09-23", "sha256": "a" * 64, "license": "CC BY-SA 4.0",
            "category": "HR", "sections": [
                {"section": "Leave > US", "anchor": "us", "section_url": "https://example.test/policy/#us",
                 "text": " ".join(f"word{number}" for number in range(120))},
                {"section": "Leave > UK", "anchor": "uk", "section_url": "https://example.test/policy/#uk",
                 "text": "The separate UK policy has a distinct eligibility condition."}]}


def test_windows_respect_budget_metadata_offsets_and_never_cross_sections():
    doc = document()
    tokenizer = OffsetTokenizer()
    chunks = chunk_document(doc, tokenizer, chunk_tokens=40, overlap_tokens=8)
    assert len(chunks) > 2
    assert len({chunk["id"] for chunk in chunks}) == len(chunks)
    for index, chunk in enumerate(chunks):
        metadata = chunk["metadata"]
        assert len(tokenizer.encode(chunk["text"])) <= 40
        assert metadata["token_count"] == len(tokenizer.encode(chunk["text"]))
        assert metadata["chunk_index"] == index
        assert all(isinstance(value, (str, int, float, bool)) for value in metadata.values())
        section = doc["sections"][metadata["section_index"]]
        raw_span = section["text"][metadata["body_char_start"]:metadata["body_char_end"]]
        assert chunk["text"].endswith(raw_span)
        assert metadata["section_url"] == section["section_url"]
        assert "UK policy" not in chunk["text"] or metadata["section_index"] == 1
    first, second = chunks[:2]
    assert second["metadata"]["body_char_start"] < first["metadata"]["body_char_end"]
    assert second["metadata"]["body_char_end"] > first["metadata"]["body_char_end"]


def test_ids_are_repeatable_and_change_with_source_snapshot():
    doc = document()
    first = chunk_document(doc, OffsetTokenizer(), 40, 8)
    assert first == chunk_document(doc, OffsetTokenizer(), 40, 8)
    doc["snapshot_date"] = "2026-09-24"
    assert [c["id"] for c in first] == [c["id"] for c in chunk_document(doc, OffsetTokenizer(), 40, 8)]
    doc["sha256"] = "b" * 64
    assert first[0]["id"] != chunk_document(doc, OffsetTokenizer(), 40, 8)[0]["id"]


def test_invalid_overlap_or_heading_budget_is_rejected():
    with pytest.raises(ValueError, match="Overlap"):
        chunk_document(document(), OffsetTokenizer(), 40, 40)
    with pytest.raises(ValueError, match="Heading"):
        chunk_document(document(), OffsetTokenizer(), 40, 39)
    with pytest.raises(ValueError, match="512"):
        chunk_document(document(), OffsetTokenizer(), 600, 64)
