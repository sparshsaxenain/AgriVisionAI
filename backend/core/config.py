"""Environment-backed application configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _boolean(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "AgriVision AI"
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'agri_vision.db'}")
    model_path: str = os.getenv("MODEL_PATH", str(ROOT_DIR / "models" / "crop_model.pt"))
    model_type: str = os.getenv("MODEL_TYPE", "pytorch")
    class_names_path: str = os.getenv("CLASS_NAMES_PATH", str(ROOT_DIR / "ml" / "class_names.json"))
    secret_key: str = os.getenv("SECRET_KEY", "development-only-change-me")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    use_mock_model: bool = _boolean("USE_MOCK_MODEL", True)
    image_size: int = int(os.getenv("IMAGE_SIZE", "224"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "8"))
    uploads_dir: Path = ROOT_DIR / "data" / "uploads"
    knowledge_dir: Path = ROOT_DIR / "knowledge"
    cors_origins: tuple[str, ...] = tuple(
        item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",") if item.strip()
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    return settings

