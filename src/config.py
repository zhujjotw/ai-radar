from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    github_token: str | None = None
    db_path: str = "./data/ai_radar.db"
    port: int = 8501
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_yaml_config(name: str) -> dict[str, Any]:
    path = ROOT_DIR / "config" / name
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a mapping")
    return data


def resolve_db_path() -> Path:
    db_path = Path(get_settings().db_path)
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    return db_path
