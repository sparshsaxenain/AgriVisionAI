"""Helpers for matching user crop records to model-supported crop families."""
from __future__ import annotations

import re


def crop_tokens(name: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", name.casefold()))


def is_model_supported(crop_name: str, supported_types: list[str]) -> bool:
    crop = crop_tokens(crop_name)
    if not crop:
        return False
    return any(crop == crop_tokens(item) for item in supported_types)
