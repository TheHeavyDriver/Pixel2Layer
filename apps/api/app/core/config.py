from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Runtime configuration, overridable via env vars / .env file."""

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

    app_name: str = "Pixel2Layer API"
    environment: Literal["development", "test", "production"] = "development"

    # Storage
    storage_backend: Literal["local", "supabase"] = "local"
    storage_dir: Path = BASE_DIR / "data" / "storage"

    # Job queue
    job_backend: Literal["memory", "redis"] = "memory"
    redis_url: str = "redis://localhost:6379/0"

    # CORS — allowed frontend origins (comma separated)
    cors_origins: str = "http://localhost:3000"

    max_upload_bytes: int = 25 * 1024 * 1024  # 25MB per frontend spec
    allowed_content_types: list[str] = ["image/png", "image/jpeg", "image/webp"]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


_settings_override: Settings | None = None


def get_settings() -> Settings:
    if _settings_override is not None:
        return _settings_override
    return Settings()