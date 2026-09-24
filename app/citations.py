"""Validate quotation provenance, then render citations from trusted metadata.

Literal quotation checks do not establish semantic entailment. A manual claim
support review remains part of evaluation.
"""
import re
from typing import Any
from urllib.parse import urlparse


class CitationValidationError(ValueError):
    pass


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _safe_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return value.replace("(", "%28").replace(")", "%29").replace(" ", "%20")


def validate_and_render(
    draft: dict[str, Any], evidence: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """Reject missing, invented or incorrectly attributed quotation support."""
    if not isinstance(draft, dict) or draft.get("sufficient") is not True:
        raise CitationValidationError("insufficient_evidence")
    claims = draft.get("claims")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 5:
        raise CitationValidationError("invalid_claims")
    by_id = {item["id"]: item for item in evidence}
    ordered_ids: list[str] = []
    rendered_claims: list[tuple[str, list[str]]] = []
    quotes_by_id: dict[str, list[str]] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            raise CitationValidationError("invalid_claim")
        text = claim.get("text")
        ids = claim.get("chunk_ids")
        quotes = claim.get("quotes")
        if not isinstance(text, str) or not text.strip() or len(text) > 1500:
            raise CitationValidationError("invalid_claim_text")
        # Sources are inserted from metadata after validation, never model output.
        if re.search(r"https?://|\[[^\]]*\]\(|\[\d+\]", text, flags=re.I):
            raise CitationValidationError("model_supplied_citation")
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
            raise CitationValidationError("missing_support_ids")
        ids = list(dict.fromkeys(ids))
        if any(i not in by_id for i in ids):
            raise CitationValidationError("unknown_support_id")
        if not isinstance(quotes, list) or not quotes:
            raise CitationValidationError("missing_support_quotes")
        quote_ids: set[str] = set()
        for quote in quotes:
            if not isinstance(quote, dict):
                raise CitationValidationError("invalid_quote")
            qid, value = quote.get("chunk_id"), quote.get("text")
            if not isinstance(qid, str) or qid not in ids:
                raise CitationValidationError("wrong_quote_source")
            if not isinstance(value, str) or not normalize_whitespace(value):
                raise CitationValidationError("empty_quote")
            normalized = normalize_whitespace(value)
            if normalized not in normalize_whitespace(by_id[qid]["text"]):
                raise CitationValidationError("quote_not_in_source")
            quote_ids.add(qid)
            quotes_by_id.setdefault(qid, []).append(normalized)
        if quote_ids != set(ids):
            raise CitationValidationError("unquoted_support_id")
        for cid in ids:
            if cid not in ordered_ids:
                ordered_ids.append(cid)
        rendered_claims.append((text.strip(), ids))

    citations: list[dict[str, Any]] = []
    for number, cid in enumerate(ordered_ids, start=1):
        item = by_id[cid]
        meta = item.get("metadata", {})
        url = _safe_url(meta.get("section_url")) or _safe_url(meta.get("source_url"))
        title = meta.get("title")
        if not url or not isinstance(title, str) or not title.strip():
            raise CitationValidationError("invalid_source_metadata")
        citations.append({
            "number": number, "chunk_id": cid,
            "document_id": meta.get("document_id", ""), "title": title,
            "url": url, "source_url": meta.get("source_url", ""),
            "section": meta.get("section", ""),
            "snapshot_date": meta.get("snapshot_date", ""),
            "quotes": list(dict.fromkeys(quotes_by_id[cid])),
        })
    numbers = {citation["chunk_id"]: citation for citation in citations}
    paragraphs = []
    for text, ids in rendered_claims:
        links = " ".join(f"[{numbers[cid]['number']}]({numbers[cid]['url']})" for cid in ids)
        paragraphs.append(f"{text} {links}")
    return "\n\n".join(paragraphs), citations

