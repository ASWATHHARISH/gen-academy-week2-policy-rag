"""Heading-aware token windows; metadata points back to exact source sections."""
from __future__ import annotations

import hashlib
from typing import Any


def chunk_document(document: dict[str, Any], tokenizer: Any,
                   chunk_tokens: int = 384, overlap_tokens: int = 64) -> list[dict[str, Any]]:
    if not 32 <= chunk_tokens <= 512:
        raise ValueError("BGE chunk size must be between 32 and 512 tokens, including special tokens.")
    if not 0 <= overlap_tokens < chunk_tokens:
        raise ValueError("Overlap must be nonnegative and smaller than chunk size.")
    chunks: list[dict[str, Any]] = []
    for section_index, section in enumerate(document["sections"]):
        body = section["text"]
        prefix = f"Document: {document['title']}\nSection: {section['section']}\n\n"
        prefix_count = len(tokenizer.encode(prefix, add_special_tokens=True))
        capacity = chunk_tokens - prefix_count
        if capacity <= overlap_tokens:
            raise ValueError(f"Heading leaves too little chunk capacity: {section['section']}")
        encoded = tokenizer(body, add_special_tokens=False, return_offsets_mapping=True)
        offsets = encoded["offset_mapping"]
        start = 0
        while start < len(offsets):
            end = min(start + capacity, len(offsets))
            char_start = offsets[start][0]
            char_end = offsets[end - 1][1]
            text = prefix + body[char_start:char_end]
            token_count = len(tokenizer.encode(text, add_special_tokens=True))
            while token_count > chunk_tokens and end > start + 1:
                end -= 1
                char_end = offsets[end - 1][1]
                text = prefix + body[char_start:char_end]
                token_count = len(tokenizer.encode(text, add_special_tokens=True))
            if token_count > chunk_tokens:
                raise ValueError("Cannot fit section text into the token budget.")
            identity = (f"{document['document_id']}|{document['sha256']}|{section_index}|"
                        f"{chunk_tokens}|{overlap_tokens}|{char_start}|{char_end}")
            chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            metadata = {key: document[key] for key in (
                "document_id", "title", "source_url", "snapshot_date", "sha256", "license")}
            metadata.update({
                "section": section["section"], "section_url": section["section_url"],
                "anchor": section["anchor"], "section_index": section_index,
                "category": document.get("category", "Policy"), "chunk_index": len(chunks),
                "chunk_id": chunk_id, "chunk_tokens": chunk_tokens, "overlap_tokens": overlap_tokens,
                "token_count": token_count, "body_char_start": char_start, "body_char_end": char_end,
            })
            chunks.append({"id": chunk_id, "text": text, "metadata": metadata})
            if end == len(offsets):
                break
            # An unusually long heading must not make the overlap cause an infinite loop.
            start = max(start + 1, end - overlap_tokens)
    return chunks
