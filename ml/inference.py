"""Convenience inference entrypoint for scripts and tests."""
from PIL import Image

from backend.core.config import get_settings
from ml.model_adapter import PredictionResult, create_model_adapter


def predict_image(image: Image.Image, source_name: str = "") -> PredictionResult:
    return create_model_adapter(get_settings()).predict(image, source_name)

