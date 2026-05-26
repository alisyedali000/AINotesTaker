"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _resolve_openai_api_key() -> str:
    """Prefer a real key from backend/.env over placeholder shell env vars."""
    file_values = dotenv_values(_ENV_PATH)
    file_key = (file_values.get("OPENAI_API_KEY") or "").strip()
    env_key = (os.environ.get("OPENAI_API_KEY") or "").strip()

    def is_placeholder(key: str) -> bool:
        return not key or key.startswith("sk-your") or key.endswith("-key")

    if file_key and not is_placeholder(file_key):
        return file_key
    if env_key and not is_placeholder(env_key):
        return env_key
    return file_key or env_key


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./tasks.db"
    cors_origins: str = "http://localhost:3000"
    host: str = "0.0.0.0"
    port: int = 8000

    # OpenAI model names
    stt_model: str = "gpt-4o-mini-transcribe"
    llm_model: str = "gpt-4.1-mini"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"

    @model_validator(mode="after")
    def apply_env_file_api_key(self) -> "Settings":
        # Pydantic may load a placeholder OPENAI_API_KEY from the shell; .env wins.
        self.openai_api_key = _resolve_openai_api_key()
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
