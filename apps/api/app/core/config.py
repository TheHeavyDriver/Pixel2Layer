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

    # Persistence (users / projects / versions)
    db_backend: Literal["memory", "postgres"] = "memory"
    postgres_url: str = "postgresql://pixel2layer:pixel2layer@localhost:5434/pixel2layer"

    # Auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 days

    # CORS — allowed frontend origins (comma separated)
    cors_origins: str = "http://localhost:3000"

    max_upload_bytes: int = 25 * 1024 * 1024  # 25MB per frontend spec
    allowed_content_types: list[str] = ["image/png", "image/jpeg", "image/webp"]

    # SAM 2 fine-tuned segmentation (see app/services/finetune)
    # Base SAM 2 checkpoint for the image encoder/predictor.
    sam2_checkpoint: Path = BASE_DIR / "data" / "finetune" / "weights" / "sam2.1_hiera_small.pt"
    # SAM 2 model config id from the sam2 package (e.g. "sam2.1_hiera_small").
    sam2_model_cfg: str = "sam2.1_hiera_small"
    # Fine-tuned LoRA weights used at runtime. When set and loadable, the
    # pipeline uses the Sam2Segmenter backend; otherwise it falls back to the
    # lightweight OpenCV VisionSegmenter.
    sam2_lora_weights: Path | None = None
    sam2_device: str = ""  # "" = auto (cuda if available else cpu)

    # Fine-tuning dataset/output locations (used by the training CLI).
    finetune_raw_dir: Path = BASE_DIR / "data" / "finetune" / "raw"
    finetune_dataset_dir: Path = BASE_DIR / "data" / "finetune" / "datasets"
    finetune_out_dir: Path = BASE_DIR / "data" / "finetune" / "weights"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


_settings_override: Settings | None = None


def get_settings() -> Settings:
    if _settings_override is not None:
        return _settings_override
    return Settings()