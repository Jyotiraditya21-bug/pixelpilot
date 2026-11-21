from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    base_url: str = "http://127.0.0.1:8000"
    gemini_api_key: SecretStr = Field(SecretStr(""), validation_alias="PP_GEMINI_API_KEY")
    vlm_model: str = Field("gemini-2.5-flash", validation_alias="PP_VLM_MODEL")
    otlp_endpoint: str | None = Field(None, validation_alias="PP_OTLP_ENDPOINT")
    runs_dir: Path = Path("runs")
    headless: bool = True


settings = Settings()
