"""The lightweight cloud entrypoint cannot switch into live generation."""
import builtins
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ui.saved_demo import load_saved_demo

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "deployment" / "replay" / "streamlit_app.py"


@pytest.mark.parametrize("question_id", ["N1", "U1", "F1"])
def test_lightweight_cloud_replay_uses_saved_responses_without_live_imports(monkeypatch, question_id):
    monkeypatch.setenv("RAG_DEMO_ONLY", "0")
    monkeypatch.setenv("RAG_CLOUD_LIVE_ENABLED", "true")
    imported = []
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "torch", "transformers", "chromadb", "langgraph", "langchain_google_genai"}:
            imported.append(name)
            raise AssertionError("Public replay must not load any live RAG dependencies")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    page = AppTest.from_file(str(ENTRYPOINT), default_timeout=15)
    page.query_params["demo"] = "0"
    page.run()
    assert not page.exception
    assert not page.text_area and not page.radio
    assert any("NOT A LIVE REQUEST" in item.value for item in page.warning)
    page.selectbox[0].select(question_id).run()
    page.button[0].click().run()
    assert not page.exception
    saved = next(example for example in load_saved_demo()["examples"] if example["id"] == question_id)
    assert page.session_state["policy_saved_result"] == saved["response"]
    assert not imported


def test_public_replay_has_only_streamlit_as_direct_dependency():
    lines = (ENTRYPOINT.parent / "requirements.txt").read_text().splitlines()
    dependencies = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    assert dependencies == ["streamlit==1.64.0"]


def test_full_protected_live_target_remains_available():
    assert (ROOT / "deployment" / "streamlit_app.py").is_file()
    requirements = (ROOT / "deployment" / "requirements.txt").read_text()
    assert "torch==2.12.1+cpu" in requirements
    assert "langchain-google-genai==4.4.0" in requirements
