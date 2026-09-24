"""Allowlisted downloads and structure-preserving HTML extraction."""
from __future__ import annotations

from copy import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from ingestion.cleaning import clean_blocks, normalize_whitespace

MANIFEST_PATH = Path(__file__).with_name("sources.json")
APPROVED_PATHS = frozenset({
    "/handbook/people-group/time-off-and-absence/time-off-types/",
    "/handbook/people-group/anti-harassment/",
    "/handbook/people-group/general-onboarding/",
    "/handbook/security/policies_and_standards/password-standard/",
    "/handbook/security/policies_and_standards/data-classification-standard/",
    "/handbook/security/security-assurance/governance/sec-training/",
    "/handbook/security/policies_and_standards/physical-security-standard-for-company-assets/",
    "/handbook/finance/expenses/",
    "/handbook/legal/anti-corruption-policy/",
    "/handbook/legal/anti-retaliation-policy/",
    "/handbook/legal/policies/gifts-contributions/",
    "/handbook/legal/ethics-compliance-program/",
})


def allowed_source_url(url: str) -> bool:
    parts = urlsplit(url)
    return (parts.scheme == "https" and parts.netloc == "handbook.gitlab.com"
            and parts.path in APPROVED_PATHS and not parts.query and not parts.fragment)


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = manifest["sources"]
    if (len(sources) != 12 or len({source["id"] for source in sources}) != 12
            or {urlsplit(source["url"]).path for source in sources} != APPROVED_PATHS
            or not all(allowed_source_url(source["url"]) for source in sources)):
        raise ValueError("Manifest must contain exactly the twelve approved GitLab pages.")
    if manifest.get("license") != "CC BY-SA 4.0":
        raise ValueError("Corpus license and attribution must be retained.")
    return manifest


def _table_lines(table: Tag) -> list[str]:
    """Repeat headers on each data row so a chunk retains column meaning."""
    result: list[str] = []
    headers: list[str] = []
    caption = table.find("caption")
    if caption:
        result.append(normalize_whitespace(caption.get_text(" ", strip=True)))
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = row.find_all(["th", "td"], recursive=False)
        values = [normalize_whitespace(cell.get_text(" ", strip=True)) for cell in cells]
        if not values:
            continue
        if all(cell.name == "th" for cell in cells):
            headers = values
            continue
        if headers and len(headers) == len(values):
            result.append(" | ".join(f"{name}: {value}" for name, value in zip(headers, values)))
        else:
            result.append(" | ".join(values))
    return result


def extract_document(html: str | bytes, source: dict[str, str], *,
                     snapshot_date: str, sha256: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".td-content") or soup.find("article") or soup.find("main")
    if article is None:
        raise ValueError(f"No article body found in {source['id']}; refusing whole-page ingestion.")
    for junk in article.select(
        "script, style, nav, footer, aside, form, button, .td-toc, #TableOfContents, "
        ".td-page-meta, .td-page-meta__lastmod, .feedback, .breadcrumb, .anchor, .edit-page"
    ):
        junk.decompose()
    sections: list[dict[str, str]] = []
    headings: list[tuple[int, str]] = []
    anchor = ""
    blocks: list[str] = []

    def flush() -> None:
        text = clean_blocks(blocks)
        if text:
            sections.append({"section": " > ".join(text for _, text in headings) or "Introduction",
                             "anchor": anchor, "section_url": source["url"] + (f"#{anchor}" if anchor else ""),
                             "text": text})
        blocks.clear()

    for node in article.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "pre", "blockquote"]):
        if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            flush()
            level = int(node.name[1])
            label = normalize_whitespace(node.get_text(" ", strip=True)).rstrip(" #")
            headings[:] = [(old_level, text) for old_level, text in headings if old_level < level]
            headings.append((level, label))
            # Never invent an anchor; preserve only an actual heading ID.
            anchor = str(node.get("id", ""))
            continue
        ancestors = [parent for parent in node.parents if parent is not article]
        if any(parent.name in {"table", "pre", "blockquote"} for parent in ancestors):
            continue
        if node.name != "li" and any(parent.name == "li" for parent in ancestors):
            continue
        if node.name == "table":
            blocks.extend(_table_lines(node))
        elif node.name == "li":
            direct = copy(node)
            for nested in direct.find_all(["ul", "ol"]):
                nested.decompose()
            text = normalize_whitespace(direct.get_text(" ", strip=True))
            if text:
                blocks.append("- " + text)
        else:
            text = normalize_whitespace(node.get_text(" ", strip=True))
            if text:
                blocks.append(text)
    flush()
    if not sections or sum(len(s["text"]) for s in sections) < 40:
        raise ValueError(f"Extracted article is empty or suspiciously short: {source['id']}")
    return {"document_id": source["id"], "title": source["title"], "source_url": source["url"],
            "category": source.get("category", "Policy"), "snapshot_date": snapshot_date,
            "sha256": sha256, "license": "CC BY-SA 4.0", "sections": sections}


def download_sources(manifest: dict[str, Any], raw_dir: Path, processed_dir: Path,
                     *, reuse_snapshots: bool = True) -> list[dict[str, Any]]:
    import httpx

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    with httpx.Client(timeout=45, follow_redirects=False,
                      headers={"User-Agent": "AcademyPolicyRAG/1.0 (public educational snapshot)"}) as client:
        for source in manifest["sources"]:
            if not allowed_source_url(source["url"]):
                raise ValueError("URL outside approved corpus.")
            raw_path = raw_dir / f"{source['id']}.html"
            record_path = raw_dir / f"{source['id']}.snapshot.json"
            if reuse_snapshots and raw_path.exists() and record_path.exists():
                body = raw_path.read_bytes()
                record = json.loads(record_path.read_text(encoding="utf-8"))
                digest = hashlib.sha256(body).hexdigest()
                if record["sha256"] != digest or record["source_url"] != source["url"]:
                    raise ValueError(f"Snapshot mismatch: {source['id']}; inspect before rebuilding.")
                timestamp = record["snapshot_date"]
            else:
                url = source["url"]
                for redirect_count in range(4):
                    with client.stream("GET", url) as response:
                        if response.is_redirect:
                            target = urljoin(url, response.headers["location"])
                            if not allowed_source_url(target):
                                raise ValueError(f"Unapproved redirect from {url} to {target}")
                            url = target
                            continue
                        response.raise_for_status()
                        if "text/html" not in response.headers.get("content-type", ""):
                            raise ValueError(f"Expected HTML for {source['id']}")
                        parts: list[bytes] = []
                        size = 0
                        for part in response.iter_bytes():
                            size += len(part)
                            if size > 8 * 1024 * 1024:
                                raise ValueError(f"Page exceeds eight-megabyte safety bound: {source['id']}")
                            parts.append(part)
                        body = b"".join(parts)
                        break
                else:
                    raise ValueError(f"Too many redirects: {source['id']}")
                digest = hashlib.sha256(body).hexdigest()
                timestamp = datetime.now(timezone.utc).isoformat()
                record = {"source_url": source["url"], "fetched_url": url, "sha256": digest,
                          "snapshot_date": timestamp, "bytes": len(body), "license": manifest["license"]}
                raw_path.write_bytes(body)
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            document = extract_document(body, source, snapshot_date=timestamp, sha256=digest)
            (processed_dir / f"{source['id']}.json").write_text(
                json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
            documents.append(document)
            print(f"Loaded {source['id']}: {len(document['sections'])} sections", flush=True)
    return documents
