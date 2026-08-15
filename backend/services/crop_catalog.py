"""Crop types derived from the crop-disease knowledge catalog."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from backend.core.config import get_settings


def _display_name(model_prefix: str) -> str:
    value = model_prefix.replace("_", " ").strip()
    if value.casefold() == "pepper, bell":
        return "Bell Pepper"
    return " ".join(value.split())


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


@lru_cache
def supported_crop_types(diseases_path: str | None = None) -> tuple[str, ...]:
    path = Path(diseases_path) if diseases_path else get_settings().knowledge_dir / "crop_diseases.json"
    try:
        disease_catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ()
    labels = disease_catalog.keys() if isinstance(disease_catalog, dict) else disease_catalog
    crops = {_display_name(str(item).split("___", 1)[0]) for item in labels if "___" in str(item)}
    return tuple(sorted(crops, key=str.casefold))


def canonical_crop_type(crop_name: str, diseases_path: str | None = None) -> str | None:
    crop = _tokens(crop_name)
    if not crop:
        return None
    return next((item for item in supported_crop_types(diseases_path) if _tokens(item) == crop), None)


def is_supported_crop_type(crop_name: str, diseases_path: str | None = None) -> bool:
    return canonical_crop_type(crop_name, diseases_path) is not None
