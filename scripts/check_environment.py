"""Report import/version availability without exposing configuration secrets."""
import importlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    # Set project-local caches and disable tracing before importing integrations.
    from app.config import get_settings

    packages = {"langchain-core": "langchain_core", "langgraph": "langgraph", "langchain-chroma": "langchain_chroma",
                "langchain-google-genai": "langchain_google_genai", "langchain-huggingface": "langchain_huggingface",
                "sentence-transformers": "sentence_transformers", "chromadb": "chromadb", "torch": "torch", "streamlit": "streamlit"}
    results = {}
    for package, module in packages.items():
        importlib.import_module(module)
        results[package] = version(package)
    settings = get_settings()
    print(json.dumps({"python": sys.version.split()[0], "executable": sys.executable,
                      "packages": results, "gemini_key_present": bool(settings.google_api_key.get_secret_value()),
                      "free_tier_confirmed": settings.gemini_free_tier_confirmed}, indent=2))


if __name__ == "__main__":
    main()
