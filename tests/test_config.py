from app.config import Settings


def test_project_dotenv_beats_ambient_key(tmp_path, monkeypatch):
    local = tmp_path / ".env"
    local.write_text("GOOGLE_API_KEY=fixture-local-key\n", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_API_KEY", "fixture-ambient-key")
    settings = Settings(_env_file=local)
    assert settings.google_api_key.get_secret_value() == "fixture-local-key"
    assert "fixture-local-key" not in repr(settings)
    assert "fixture-local-key" not in settings.model_dump_json()


def test_explicit_settings_override_project_env(tmp_path):
    local = tmp_path / ".env"
    local.write_text("EVIDENCE_THRESHOLD=0.9\n", encoding="utf-8")
    settings = Settings(_env_file=local, evidence_threshold=0.4)
    assert settings.evidence_threshold == 0.4
