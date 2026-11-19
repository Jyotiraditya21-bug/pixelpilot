from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    base_url: str = "http://127.0.0.1:8000"
    ollama_url: str = Field("http://127.0.0.1:11434", validation_alias="PP_OLLAMA_HOST")
    ollama_model: str = Field("qwen2.5vl:3b", validation_alias="PP_VLM_MODEL")
    otlp_endpoint: str | None = Field(None, validation_alias="PP_OTLP_ENDPOINT")
    runs_dir: Path = Path("runs")
    headless: bool = True


settings = Settings()
