"""Application lifecycle wrapper for crop inference."""
from backend.core.config import get_settings
from ml.model_adapter import BaseCropModelAdapter, create_model_adapter

_adapter: BaseCropModelAdapter | None = None
_load_error: str | None = None


def get_crop_model() -> BaseCropModelAdapter:
    global _adapter, _load_error
    if _adapter is None:
        try:
            _adapter = create_model_adapter(get_settings())
        except Exception as exc:
            _load_error = str(exc)
            raise
    return _adapter


def model_status() -> dict:
    try:
        adapter = get_crop_model()
        return {"loaded": adapter.loaded, "mock_mode": adapter.is_mock, "error": _load_error}
    except Exception as exc:
        return {"loaded": False, "mock_mode": False, "error": str(exc)}

