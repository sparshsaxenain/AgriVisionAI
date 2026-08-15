"""Replaceable crop-disease inference adapters.

All model-specific behavior ends at PredictionResult. The API and UI never consume
raw framework tensors.
"""
from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ml.preprocessing import resize_to_array


@dataclass(frozen=True)
class PredictionItem:
    class_name: str
    display_name: str
    confidence: float


@dataclass(frozen=True)
class PredictionResult:
    predicted_class: str
    display_name: str
    confidence: float
    top_predictions: list[PredictionItem]
    model_version: str
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def friendly_name(label: str) -> str:
    return label.replace("___", " ").replace("__", " ").replace("_", " ").strip().title()


def load_class_names(path: str | Path) -> list[str]:
    content = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(content, dict):
        return [content[str(i)] for i in range(len(content))]
    return list(content)


class BaseCropModelAdapter(ABC):
    is_mock = False

    @abstractmethod
    def load_model(self) -> None: ...

    @abstractmethod
    def preprocess(self, image: Image.Image) -> Any: ...

    @abstractmethod
    def predict(self, image: Image.Image, source_name: str = "") -> PredictionResult: ...

    @property
    @abstractmethod
    def loaded(self) -> bool: ...


class MockCropModelAdapter(BaseCropModelAdapter):
    """Deterministic, realistic demo adapter used when no supplied model is present."""

    is_mock = True
    classes = ["Tomato___Early_blight", "Tomato___healthy", "Potato___Late_blight"]

    def load_model(self) -> None:
        return None

    @property
    def loaded(self) -> bool:
        return True

    def preprocess(self, image: Image.Image) -> np.ndarray:
        return resize_to_array(image, 224)

    def predict(self, image: Image.Image, source_name: str = "") -> PredictionResult:
        started = time.perf_counter()
        digest = hashlib.sha256((source_name or "demo").lower().encode()).digest()[0]
        # The default and tomato sample path reproduce the hackathon's scripted result.
        if "healthy" in source_name.lower():
            values = [0.035, 0.932, 0.033]
        elif "potato" in source_name.lower():
            values = [0.041, 0.028, 0.931]
        else:
            values = [0.946, 0.032 + (digest % 3) / 1000, 0.022 - (digest % 3) / 1000]
        ranked = sorted(zip(self.classes, values), key=lambda item: item[1], reverse=True)
        top = [PredictionItem(name, friendly_name(name), round(score, 4)) for name, score in ranked]
        return PredictionResult(
            predicted_class=top[0].class_name,
            display_name=top[0].display_name,
            confidence=top[0].confidence,
            top_predictions=top,
            model_version="mock-demo-1.0",
            inference_time_ms=round((time.perf_counter() - started) * 1000 + 18.4, 1),
        )


class PyTorchCropModelAdapter(BaseCropModelAdapter):
    """Adapter for TorchScript or serialized nn.Module artifacts.

    A raw state_dict cannot be reconstructed without its architecture; in that case
    export TorchScript or add a small project-specific adapter as documented.
    """

    def __init__(self, model_path: str, class_names_path: str, image_size: int = 224):
        self.model_path = Path(model_path)
        self.class_names = load_class_names(class_names_path)
        self.image_size = image_size
        self.model: Any = None
        self._torch: Any = None

    def load_model(self) -> None:
        import torch

        self._torch = torch
        try:
            self.model = torch.jit.load(str(self.model_path), map_location="cpu")
        except Exception:
            self.model = torch.load(str(self.model_path), map_location="cpu", weights_only=False)
        if not hasattr(self.model, "eval"):
            raise ValueError("Model artifact is a state_dict. Export TorchScript or supply an architecture adapter.")
        self.model.eval()

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def preprocess(self, image: Image.Image) -> Any:
        array = resize_to_array(image, self.image_size)
        # Defaults are intentionally neutral. Configure a custom adapter if training used normalization.
        return self._torch.from_numpy(array.transpose(2, 0, 1)).unsqueeze(0)

    def predict(self, image: Image.Image, source_name: str = "") -> PredictionResult:
        started = time.perf_counter()
        tensor = self.preprocess(image)
        with self._torch.no_grad():
            output = self.model(tensor)
        if isinstance(output, dict):
            output = output.get("logits", next(iter(output.values())))
        if hasattr(output, "logits"):
            output = output.logits
        probabilities = self._torch.softmax(output, dim=-1)[0].cpu().numpy()
        order = np.argsort(probabilities)[::-1][:3]
        top = [
            PredictionItem(self.class_names[i], friendly_name(self.class_names[i]), float(probabilities[i]))
            for i in order
        ]
        return PredictionResult(
            top[0].class_name, top[0].display_name, top[0].confidence, top,
            self.model_path.name, round((time.perf_counter() - started) * 1000, 1),
        )


class KerasCropModelAdapter(BaseCropModelAdapter):
    def __init__(self, model_path: str, class_names_path: str, image_size: int = 224):
        self.model_path = Path(model_path)
        self.class_names = load_class_names(class_names_path)
        self.image_size = image_size
        self.model: Any = None

    def load_model(self) -> None:
        from tensorflow import keras

        self.model = keras.models.load_model(self.model_path)

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def preprocess(self, image: Image.Image) -> np.ndarray:
        return np.expand_dims(resize_to_array(image, self.image_size), axis=0)

    def predict(self, image: Image.Image, source_name: str = "") -> PredictionResult:
        started = time.perf_counter()
        raw = np.asarray(self.model.predict(self.preprocess(image), verbose=0))[0]
        exp = np.exp(raw - np.max(raw))
        probabilities = exp / exp.sum()
        order = np.argsort(probabilities)[::-1][:3]
        top = [PredictionItem(self.class_names[i], friendly_name(self.class_names[i]), float(probabilities[i])) for i in order]
        return PredictionResult(top[0].class_name, top[0].display_name, top[0].confidence, top, self.model_path.name, round((time.perf_counter() - started) * 1000, 1))


class MobileNetV3CropModelAdapter(BaseCropModelAdapter):
    """Adapter for the fine-tuned MobileNetV3-Large plant disease classifier.

    This adapter reconstructs the exact architecture used during training
    (mobilenet_v3_large with a 38-class classifier head), loads the saved
    state_dict checkpoint, and applies ImageNet normalization during
    preprocessing to match the training pipeline.
    """

    IMAGENET_MEAN = [0.485, 0.456, 0.406]
    IMAGENET_STD = [0.229, 0.224, 0.225]

    def __init__(self, model_path: str, class_names_path: str, image_size: int = 224):
        self.model_path = Path(model_path)
        self.class_names = load_class_names(class_names_path)
        self.image_size = image_size
        self.num_classes = len(self.class_names)
        self.model: Any = None
        self._torch: Any = None
        self._transforms: Any = None

    def load_model(self) -> None:
        import torch
        import torch.nn as nn
        from torchvision import models, transforms

        self._torch = torch
        self._transforms = transforms

        # Reconstruct the exact architecture used during training.
        model = models.mobilenet_v3_large(weights=None)
        model.classifier[3] = nn.Linear(model.classifier[3].in_features, self.num_classes)

        # Load the state_dict checkpoint.
        checkpoint = torch.load(str(self.model_path), map_location="cpu", weights_only=False)
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            model.load_state_dict(checkpoint["state_dict"])
        elif isinstance(checkpoint, dict):
            model.load_state_dict(checkpoint)
        else:
            raise ValueError("Unexpected checkpoint format for MobileNetV3 adapter.")
        model.eval()
        self.model = model

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def preprocess(self, image: Image.Image) -> Any:
        """Apply the same preprocessing pipeline used during training:
        Resize → ToTensor ([0,1]) → ImageNet Normalize.
        """
        transform = self._transforms.Compose([
            self._transforms.Resize((self.image_size, self.image_size)),
            self._transforms.ToTensor(),
            self._transforms.Normalize(self.IMAGENET_MEAN, self.IMAGENET_STD),
        ])
        return transform(image.convert("RGB")).unsqueeze(0)

    def predict(self, image: Image.Image, source_name: str = "") -> PredictionResult:
        started = time.perf_counter()
        tensor = self.preprocess(image)
        with self._torch.no_grad():
            output = self.model(tensor)
        probabilities = self._torch.softmax(output, dim=-1)[0].cpu().numpy()
        order = np.argsort(probabilities)[::-1][:3]
        top = [
            PredictionItem(self.class_names[i], friendly_name(self.class_names[i]), float(probabilities[i]))
            for i in order
        ]
        return PredictionResult(
            top[0].class_name, top[0].display_name, top[0].confidence, top,
            self.model_path.name, round((time.perf_counter() - started) * 1000, 1),
        )


def create_model_adapter(settings: Any) -> BaseCropModelAdapter:
    model_exists = Path(settings.model_path).exists()
    if settings.use_mock_model or not model_exists:
        adapter: BaseCropModelAdapter = MockCropModelAdapter()
    elif settings.model_type.lower() in {"mobilenetv3", "mobilenet_v3"}:
        adapter = MobileNetV3CropModelAdapter(settings.model_path, settings.class_names_path, settings.image_size)
    elif settings.model_type.lower() in {"keras", "tensorflow", "h5", "savedmodel"}:
        adapter = KerasCropModelAdapter(settings.model_path, settings.class_names_path, settings.image_size)
    else:
        adapter = PyTorchCropModelAdapter(settings.model_path, settings.class_names_path, settings.image_size)
    adapter.load_model()
    return adapter

