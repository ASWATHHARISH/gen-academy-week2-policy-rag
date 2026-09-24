"""Explicit one-attempt smoke check. Never invoked on application startup."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.citations import validate_and_render
from app.config import get_settings
from app.generation import GenerationError, generate


def main() -> int:
    parser = argparse.ArgumentParser(description="Spend at most one shared-budget Gemini attempt.")
    parser.add_argument("--max-calls", type=int, choices=[1], required=True)
    parser.parse_args()
    evidence = [{"id": "smoke-1", "text": "The demo policy colour is blue.", "score": 1.0,
                 "metadata": {"title": "Local smoke fixture", "document_id": "smoke",
                              "source_url": "https://example.com/smoke-fixture"}}]
    try:
        draft = generate("What is the demo policy colour?", evidence, get_settings())
        validate_and_render(draft, evidence)
        print("Gemini smoke check passed (one shared-budget attempt).")
        return 0
    except GenerationError as error:
        print(f"Gemini smoke check failed: {error.code}; api_called={error.api_called}")
    except Exception:
        print("Gemini smoke check failed: invalid_grounded_response")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

