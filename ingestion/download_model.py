"""Explicit, selective download of the approved BGE model; never run on app startup."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json

from app.config import get_settings

APPROVED_MODEL = "BAAI/bge-small-en-v1.5"
APPROVED_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
ALLOW_PATTERNS = ["model.safetensors", "config.json", "modules.json", "sentence_bert_config.json",
                  "config_sentence_transformers.json", "tokenizer.json", "tokenizer_config.json",
                  "special_tokens_map.json", "vocab.txt", "1_Pooling/config.json", "README.md"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=APPROVED_MODEL, choices=[APPROVED_MODEL])
    args = parser.parse_args()
    settings = get_settings()
    target = settings.embedding_dir
    manifest_path = target / "download-manifest.json"
    from huggingface_hub import snapshot_download

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("model") != args.model:
            raise ValueError("Existing model manifest does not match the approved model.")
        revision = manifest["revision"]
        # Reuse a complete snapshot with verified hashes, without contacting Hugging Face.
        if manifest.get("files") and all(
            (target / item["path"]).is_file()
            and hashlib.sha256((target / item["path"]).read_bytes()).hexdigest() == item["sha256"]
            for item in manifest["files"]
        ):
            print(f"Verified local model {args.model} at revision {revision}.")
            return
    else:
        revision = APPROVED_REVISION
    snapshot_download(repo_id=args.model, revision=revision, local_dir=str(target),
                      allow_patterns=ALLOW_PATTERNS, max_workers=4, token=False)
    if not (target / "model.safetensors").is_file() or not (target / "tokenizer.json").is_file():
        raise ValueError("Model download is incomplete; safetensors weights/tokenizer are required.")
    files = [{"path": path.relative_to(target).as_posix(), "bytes": path.stat().st_size,
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted(target.rglob("*")) if path.is_file()
             and ".cache" not in path.relative_to(target).parts and path != manifest_path]
    manifest = {"model": args.model, "revision": revision, "license": "MIT",
                "downloaded_at": datetime.now(timezone.utc).isoformat(), "files": files,
                "total_bytes": sum(item["bytes"] for item in files)}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Downloaded {args.model} at revision {revision}: {manifest['total_bytes']:,} bytes.")


if __name__ == "__main__":
    main()
