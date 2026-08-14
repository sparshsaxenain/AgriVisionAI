"""Model-agnostic image validation and preprocessing helpers."""
from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image, ImageOps


def open_rgb_image(data: bytes) -> Image.Image:
    image = Image.open(BytesIO(data))
    image.verify()
    image = Image.open(BytesIO(data))
    return ImageOps.exif_transpose(image).convert("RGB")


def resize_to_array(image: Image.Image, size: int) -> np.ndarray:
    resized = ImageOps.fit(image, (size, size), method=Image.Resampling.LANCZOS)
    return np.asarray(resized, dtype=np.float32) / 255.0

