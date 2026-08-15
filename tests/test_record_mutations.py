from io import BytesIO
from pathlib import Path

from PIL import Image

from backend.core.config import get_settings


def test_farm_patch_changes_only_requested_property(client, auth_headers):
    farm = client.post(
        "/farms",
        headers=auth_headers,
        json={"farm_name": "Jodhpur Farm", "village": "Jodhpur", "total_area": 4, "irrigation_type": "Canal"},
    ).json()

    response = client.patch(f"/farms/{farm['id']}", headers=auth_headers, json={"status": "Dry"})

    assert response.status_code == 200
    assert response.json()["status"] == "Dry"
    assert response.json()["farm_name"] == "Jodhpur Farm"
    assert response.json()["irrigation_type"] == "Canal"


def test_animal_patch_and_confirmed_delete(client, auth_headers):
    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Animal Farm"}).json()
    animal = client.post(
        "/livestock",
        headers=auth_headers,
        json={"farm_id": farm["id"], "animal_type": "Cow", "tag_id": "COW-44", "name": "Gauri"},
    ).json()

    updated = client.patch(
        f"/livestock/{animal['id']}",
        headers=auth_headers,
        json={"name": "Gauri Devi", "status": "Under treatment", "weight": 410},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Gauri Devi"
    assert updated.json()["tag_id"] == "COW-44"

    rejected = client.delete(
        f"/livestock/{animal['id']}", headers=auth_headers, params={"confirm_tag_id": "wrong"}
    )
    assert rejected.status_code == 400
    deleted = client.delete(
        f"/livestock/{animal['id']}", headers=auth_headers, params={"confirm_tag_id": "COW-44"}
    )
    assert deleted.status_code == 204
    assert client.get("/livestock", headers=auth_headers).json() == []


def test_confirmed_farm_delete_cascades_crops_and_livestock(client, auth_headers):
    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Temporary Farm"}).json()
    client.post("/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Tomato"})
    client.post(
        "/livestock",
        headers=auth_headers,
        json={"farm_id": farm["id"], "animal_type": "Goat", "tag_id": "GOAT-TEMP"},
    )

    rejected = client.delete(
        f"/farms/{farm['id']}", headers=auth_headers, params={"confirm_name": "Not the farm"}
    )
    assert rejected.status_code == 400
    deleted = client.delete(
        f"/farms/{farm['id']}", headers=auth_headers, params={"confirm_name": "Temporary Farm"}
    )
    assert deleted.status_code == 204
    assert client.get("/farms", headers=auth_headers).json() == []
    assert client.get("/crops", headers=auth_headers).json() == []
    assert client.get("/livestock", headers=auth_headers).json() == []


def test_supported_crop_types_come_from_disease_catalog(client):
    response = client.get("/diagnosis/supported-crops")
    assert response.status_code == 200
    assert response.json() == [
        "Apple", "Bell Pepper", "Blueberry", "Cherry (including sour)", "Corn (maize)",
        "Grape", "Orange", "Peach", "Potato", "Raspberry", "Soybean", "Squash",
        "Strawberry", "Tomato",
    ]


def test_crop_creation_and_rename_only_accept_disease_catalog_types(client, auth_headers):
    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Catalog Farm"}).json()

    rejected = client.post(
        "/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Wheat"}
    )
    assert rejected.status_code == 400
    assert "Unsupported crop type" in rejected.json()["detail"]

    created = client.post(
        "/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "tomato"}
    )
    assert created.status_code == 201
    assert created.json()["crop_name"] == "Tomato"

    renamed = client.patch(
        f"/crops/{created.json()['id']}",
        headers=auth_headers,
        json={"crop_name": "pepper, bell", "variety": "California Wonder", "crop_stage": "Fruiting"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["crop_name"] == "Bell Pepper"
    assert renamed.json()["variety"] == "California Wonder"

    invalid_rename = client.patch(
        f"/crops/{created.json()['id']}", headers=auth_headers, json={"crop_name": "Rice"}
    )
    assert invalid_rename.status_code == 400
    assert client.get(f"/crops/{created.json()['id']}", headers=auth_headers).json()["crop_name"] == "Bell Pepper"


def test_crop_cycle_patch_can_move_farm_and_clear_dates(client, auth_headers):
    first = client.post("/farms", headers=auth_headers, json={"farm_name": "First Farm"}).json()
    second = client.post("/farms", headers=auth_headers, json={"farm_name": "Second Farm"}).json()
    crop = client.post(
        "/crops",
        headers=auth_headers,
        json={"farm_id": first["id"], "crop_name": "Potato", "sowing_date": "2026-07-01"},
    ).json()

    response = client.patch(
        f"/crops/{crop['id']}",
        headers=auth_headers,
        json={"farm_id": second["id"], "sowing_date": None, "status": "Completed", "area": 3.5},
    )

    assert response.status_code == 200
    assert response.json()["farm_id"] == second["id"]
    assert response.json()["sowing_date"] is None
    assert response.json()["status"] == "Completed"
    assert response.json()["area"] == 3.5


def test_confirmed_crop_delete_cascades_diagnoses_alerts_and_image(client, auth_headers):
    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Crop Delete Farm"}).json()
    crop = client.post(
        "/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Tomato"}
    ).json()
    image = BytesIO()
    Image.new("RGB", (80, 80), "green").save(image, "JPEG")
    preview = client.post(
        "/diagnosis/predict",
        headers=auth_headers,
        data={"farm_id": farm["id"], "crop_id": crop["id"]},
        files={"image": ("tomato.jpg", image.getvalue(), "image/jpeg")},
    ).json()
    saved = client.post(
        "/diagnosis/save",
        headers=auth_headers,
        json={
            "farm_id": farm["id"],
            "crop_id": crop["id"],
            "image_token": preview["image_token"],
            "predicted_class": preview["predicted_class"],
            "display_name": preview["display_name"],
            "confidence": preview["confidence"],
            "severity": preview["severity"],
            "advisory": preview["advisory"],
            "model_version": preview["model_version"],
        },
    )
    assert saved.status_code == 201
    image_path = Path(get_settings().uploads_dir) / preview["image_token"]
    assert image_path.exists()

    rejected = client.delete(
        f"/crops/{crop['id']}", headers=auth_headers, params={"confirm_name": "Potato"}
    )
    assert rejected.status_code == 400
    deleted = client.delete(
        f"/crops/{crop['id']}", headers=auth_headers, params={"confirm_name": "Tomato"}
    )

    assert deleted.status_code == 204
    assert client.get("/crops", headers=auth_headers).json() == []
    assert client.get("/diagnosis/history", headers=auth_headers).json() == []
    assert client.get("/alerts", headers=auth_headers, params={"include_read": True}).json() == []
    assert not image_path.exists()


def test_due_vaccinations_returns_global_results_for_all_animals(client, auth_headers):
    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Vaccination Farm"}).json()
    cow = client.post(
        "/livestock",
        headers=auth_headers,
        json={"farm_id": farm["id"], "animal_type": "Cow", "tag_id": "VAC-COW", "name": "Gauri"},
    ).json()
    goat = client.post(
        "/livestock",
        headers=auth_headers,
        json={"farm_id": farm["id"], "animal_type": "Goat", "tag_id": "VAC-GOAT", "name": "Meera"},
    ).json()
    client.post(
        f"/livestock/{cow['id']}/vaccination",
        headers=auth_headers,
        json={"vaccine_name": "FMD", "due_date": (date.today() - timedelta(days=1)).isoformat()},
    )
    client.post(
        f"/livestock/{goat['id']}/vaccination",
        headers=auth_headers,
        json={"vaccine_name": "PPR", "due_date": (date.today() + timedelta(days=20)).isoformat()},
    )
    client.post(
        f"/livestock/{goat['id']}/vaccination",
        headers=auth_headers,
        json={
            "vaccine_name": "Completed vaccine",
            "administered_date": date.today().isoformat(),
            "due_date": date.today().isoformat(),
        },
    )

    response = client.get("/livestock/vaccinations/due", headers=auth_headers)

    assert response.status_code == 200
    assert [(item["animal"], item["vaccine_name"]) for item in response.json()] == [("Gauri", "FMD"), ("Meera", "PPR")]
    assert response.json()[0]["status"] == "Overdue"
from datetime import date, timedelta
