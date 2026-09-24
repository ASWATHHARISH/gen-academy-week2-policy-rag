"""Create a secret-free source/snapshot ZIP; no model, venv, DB or API ledger."""
from pathlib import Path
import argparse
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("app", "ingestion", "evaluation", "ui", "scripts", "tests", "docs", ".streamlit", "deployment")
ROOT_FILES = ("README.md", "architecture.md", "THIRD_PARTY_NOTICES.md", "requirements.txt", "requirements-lock.txt", ".gitignore", ".gitattributes", ".env.example")


def selected_files():
    for name in ROOT_FILES:
        path = ROOT / name
        if path.is_file():
            yield path
    for name in SOURCE_DIRS:
        for path in sorted((ROOT / name).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".ps1", ".mjs", ".json", ".jsonl", ".csv", ".md", ".toml", ".svg", ".txt", ".srt"} and "__pycache__" not in path.parts and not path.name.startswith("secrets."):
                yield path
    # Public frozen snapshots preserve the measured corpus when pages change.
    for name in ("data/raw", "data/processed"):
        for path in sorted((ROOT / name).rglob("*")):
            if path.is_file() and path.suffix in {".html", ".json", ".jsonl"}:
                yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="enterprise-policy-rag-source.zip")
    args = parser.parse_args()
    if Path(args.name).name != args.name or not args.name.endswith(".zip") or "/" in args.name or "\\" in args.name:
        raise ValueError("Archive name must be a simple ZIP filename inside artifacts.")
    destination = ROOT / "artifacts" / args.name
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        raise FileExistsError("Submission archive already exists; choose a new name instead of overwriting it.")
    files = list(selected_files())
    forbidden = {".env", "api_budget.json", "api_budget.json.lock"}
    assert all(path.name not in forbidden for path in files)
    sys.path.insert(0, str(ROOT))
    from app.config import get_settings
    secret = get_settings().google_api_key.get_secret_value().encode("utf-8")
    if secret and any(secret in path.read_bytes() for path in files):
        raise ValueError("Packaging stopped: a source artifact contains the configured secret.")
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, "enterprise-policy-rag/" + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
    print(f"Created {destination.name}: {len(files)} source/documentation/result/public-snapshot files; no .env, model, venv, database or API ledger.")


if __name__ == "__main__":
    main()
