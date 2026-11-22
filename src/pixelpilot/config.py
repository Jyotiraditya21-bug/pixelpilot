from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    base_url: str = "http://127.0.0.1:8000"
    gemini_api_key: SecretStr = Field(SecretStr(""), validation_alias="PP_GEMINI_API_KEY")
    vlm_model: str = Field("gemini-3-flash-preview", validation_alias="PP_VLM_MODEL")
    otlp_endpoint: str | None = Field(None, validation_alias="PP_OTLP_ENDPOINT")
    runs_dir: Path = Path("runs")
    headless: bool = True


settings = Settings()


def redact_secrets(message: str, *additional_values: str | None) -> str:
    """Remove configured and operation-local secrets from diagnostic text."""
    configured_key = settings.gemini_api_key.get_secret_value()
    secrets = {value for value in (configured_key, *additional_values) if value}
    redacted = message
    for secret in sorted(secrets, key=len, reverse=True):
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def allowed_navigation_hosts() -> frozenset[str]:
    configured_host = urlsplit(settings.base_url).hostname
    return frozenset(host for host in (configured_host, "localhost", "127.0.0.1", "::1") if host)


def validate_navigation_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("navigation URL scheme is not allowlisted")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("navigation URL credentials are forbidden")
    if parsed.hostname not in allowed_navigation_hosts():
        raise ValueError("navigation URL host is not in the allowlist")
