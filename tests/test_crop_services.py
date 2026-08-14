from PIL import Image

from backend.services.advisory_service import AdvisoryService
from ml.model_adapter import MockCropModelAdapter


def test_mock_model_returns_normalized_prediction():
    result = MockCropModelAdapter().predict(Image.new("RGB", (64, 64), "green"), "tomato_leaf.jpg")
    assert result.predicted_class == "Tomato___Early_blight"
    assert result.confidence == 0.946
    assert len(result.top_predictions) == 3


def test_advisory_maps_label_and_confidence():
    advice = AdvisoryService().build("Tomato___Early_blight", 0.94, "Tomato", "Fruiting")
    assert advice["condition"] == "Tomato Early Blight"
    assert advice["confidence_label"] == "High confidence"
    assert advice["recommended_actions"]


def test_low_confidence_escalates():
    advice = AdvisoryService().build("Tomato___Early_blight", 0.42)
    assert "expert verification" in advice["confidence_label"].lower()

