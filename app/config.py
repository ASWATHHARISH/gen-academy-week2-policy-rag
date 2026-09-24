"""Project-local configuration. Secret values must never enter logs."""
from functools import lru_cache
import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

# All runtime caches stay in this project. Never change the user's profile.
os.environ["HF_HOME"] = str(ROOT / ".cache" / "huggingface")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # Prefer this project's .env over unrelated ambient provider credentials.
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    google_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    google_model: str = "gemini-3.5-flash-lite"
    gemini_free_tier_confirmed: bool = False
    max_api_attempts: int = 30
    api_min_interval_seconds: float = 5.0
    evidence_threshold: float = 0.65  # Provisional; calibrate on development questions only.
    retrieval_mode: str = "hybrid"  # P1 default; app.profiles retains the P0 configuration.
    gate_mode: str = "p1"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    chunk_tokens: int = 256
    overlap_tokens: int = 48
    collection_name: str = "gitlab_policy_bge_256"
    retrieval_k: int = 10
    evidence_k: int = 5
    embedding_dir: Path = ROOT / ".cache" / "models" / "bge-small-en-v1.5"
    chroma_dir: Path = ROOT / "data" / "chroma"
    chunks_path: Path = ROOT / "data" / "processed" / "chunks256" / "chunks.jsonl"
    api_budget_path: Path = ROOT / "data" / "api_budget.json"
    calibration_path: Path = ROOT / "evaluation" / "results" / "calibration_p1_256.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
