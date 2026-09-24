"""Lightweight public replay: no live-mode switch, secrets, models, or API calls."""
from pathlib import Path
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Deliberately unconditional: query parameters, environment variables, or cloud
# secrets cannot enable live generation on this Streamlit-only deployment.
os.environ["RAG_DEMO_ONLY"] = "1"
runpy.run_path(str(ROOT / "ui" / "streamlit_app.py"), run_name="__main__")
