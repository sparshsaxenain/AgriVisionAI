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
    nvidia_nim_base_url: str = os.getenv(
        "NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"
    ).rstrip("/")
    nvidia_nim_api_key: str = os.getenv("NVIDIA_API_KEY", "").strip()
    nvidia_nim_model: str = os.getenv("NVIDIA_NIM_MODEL", "nvidia/nemotron-3-nano-30b-a3b")
    nvidia_nim_max_tokens: int = int(os.getenv("NVIDIA_NIM_MAX_TOKENS", "768"))
    agent_max_steps: int = int(os.getenv("AGENT_MAX_STEPS", "8"))
    agent_timeout_seconds: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "180"))
    agent_context_window: int = int(os.getenv("AGENT_CONTEXT_WINDOW", "8192"))
    ood_confidence_threshold: float = float(os.getenv("OOD_CONFIDENCE_THRESHOLD", "0.45"))
    ood_entropy_threshold: float = float(os.getenv("OOD_ENTROPY_THRESHOLD", "2.5"))
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
