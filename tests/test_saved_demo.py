"""Saved replay must render real records without model or API execution."""
import builtins
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ui.saved_demo import DEFAULT_RESULTS, demo_only_enabled, load_saved_demo

UI_PATH = Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py"


def test_saved_examples_are_exact_copies_of_actual_evaluation_responses():
    recorded = json.loads(DEFAULT_RESULTS.read_text(encoding="utf-8"))
    actual = {row["id"]: row for row in recorded["rows"]}
    loaded = load_saved_demo()
    assert [row["id"] for row in loaded["examples"]] == ["N1", "U1", "F1"]
    for example in loaded["examples"]:
        assert example["question"] == actual[example["id"]]["question"]
        assert example["response"] == actual[example["id"]]["response"]


def test_missing_required_demo_record_is_an_error_not_an_invented_answer(tmp_path):
    path = tmp_path / "missing.json"
    path.write_text(json.dumps({"rows": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        load_saved_demo(path)


@pytest.mark.parametrize("value,enabled", [("1", True), ("true", True), ("0", False), ("", False)])
def test_demo_only_environment_switch(monkeypatch, value, enabled):
    monkeypatch.setenv("RAG_DEMO_ONLY", value)
    assert demo_only_enabled() is enabled


def test_demo_only_has_no_live_form_or_model_import_and_displays_saved_latency(monkeypatch):
    monkeypatch.setenv("RAG_DEMO_ONLY", "1")
    original_import = builtins.__import__
    forbidden_imports = []

    def guarded_import(name, *args, **kwargs):
        if name in {"app.config", "app.graph", "app.embeddings", "torch", "transformers"}:
            forbidden_imports.append(name)
            raise AssertionError("Replay must not import model or live configuration dependencies.")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    page = AppTest.from_file(str(UI_PATH), default_timeout=10).run()
    assert not page.exception
    assert not page.text_area
    assert not page.radio
    assert page.button[0].label == "Show saved result"
    assert any("NOT A LIVE REQUEST" in warning.value for warning in page.warning)
    page.button[0].click().run()
    assert not page.exception
    actual = load_saved_demo()["examples"][0]["response"]
    assert page.session_state["policy_saved_result"] == actual
    assert any(item.value == actual["answer"] for item in page.markdown)
    assert any("Recorded response time from the saved run" in item.value for item in page.caption)
    assert not forbidden_imports
    page.selectbox[0].select("U1").run()
    page.button[0].click().run()
    assert not page.exception
    assert page.session_state["policy_saved_result"]["status"] == "fallback"
    assert not forbidden_imports


def test_demo_query_parameter_defaults_to_replay_without_disabling_local_live_mode(monkeypatch):
    monkeypatch.delenv("RAG_DEMO_ONLY", raising=False)
    page = AppTest.from_file(str(UI_PATH), default_timeout=10)
    page.query_params["demo"] = "1"
    page.run()
    assert not page.exception
    assert page.radio[0].value == "Saved evaluation replay"
    assert not page.text_area
    page.radio[0].set_value("Live questions").run()
    assert not page.exception
    assert page.text_area
    assert page.button[0].label == "Find an answer"
