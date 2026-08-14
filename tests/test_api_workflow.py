from io import BytesIO

from PIL import Image


def _image_bytes():
    buffer = BytesIO()
    Image.new("RGB", (120, 120), "green").save(buffer, "JPEG")
    return buffer.getvalue()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is True


def test_crop_diagnosis_end_to_end(client, auth_headers):
    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Demo Farm", "total_area": 1}).json()
    crop = client.post("/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Tomato", "crop_stage": "Fruiting"}).json()
    predicted = client.post("/diagnosis/predict", headers=auth_headers, data={"farm_id": farm["id"], "crop_id": crop["id"]}, files={"image": ("tomato_leaf.jpg", _image_bytes(), "image/jpeg")})
    assert predicted.status_code == 200
    result = predicted.json()
    saved = client.post("/diagnosis/save", headers=auth_headers, json={"farm_id": farm["id"], "crop_id": crop["id"], "image_token": result["image_token"], "predicted_class": result["predicted_class"], "display_name": result["display_name"], "confidence": result["confidence"], "severity": result["severity"], "advisory": result["advisory"], "model_version": result["model_version"]})
    assert saved.status_code == 201
    history = client.get("/diagnosis/history", headers=auth_headers)
    assert len(history.json()) == 1

