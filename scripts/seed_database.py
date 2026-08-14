"""Create an immediately usable AgriVision AI demo database."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from backend.core.security import hash_password
from backend.db.database import SessionLocal, init_db
from backend.models import (
    Alert, Crop, CropDiagnosis, Farm, Livestock, LivestockMedicalRecord,
    LivestockObservation, User, VaccinationRecord,
)


def seed() -> None:
    init_db()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == "farmer@example.com"))
        if existing:
            print("Demo data already exists. Login: farmer@example.com / demo123")
            return
        farmer = User(
            name="Ravi Kumar", phone="9876543210", email="farmer@example.com",
            password_hash=hash_password("demo123"), preferred_language="en",
            village="Kaveripatti", district="Krishnagiri", state="Tamil Nadu",
        )
        db.add(farmer)
        db.flush()
        farm = Farm(
            farmer_id=farmer.id, farm_name="Green Valley Farm", village="Kaveripatti",
            district="Krishnagiri", state="Tamil Nadu", latitude=12.5266,
            longitude=78.2138, total_area=5.5, area_unit="acres",
            soil_type="Red loam", irrigation_type="Drip + borewell",
        )
        db.add(farm)
        db.flush()
        today = date.today()
        crops = [
            Crop(farm_id=farm.id, crop_name="Tomato", variety="Arka Rakshak", sowing_date=today - timedelta(days=62), expected_harvest_date=today + timedelta(days=28), area=2.0, crop_stage="Fruiting", status="Active", notes="Drip irrigated"),
            Crop(farm_id=farm.id, crop_name="Paddy", variety="CO 51", sowing_date=today - timedelta(days=35), expected_harvest_date=today + timedelta(days=80), area=2.5, crop_stage="Vegetative", status="Active", notes="Field transplanted"),
            Crop(farm_id=farm.id, crop_name="Groundnut", variety="TMV 13", sowing_date=today - timedelta(days=28), expected_harvest_date=today + timedelta(days=78), area=1.0, crop_stage="Flowering", status="Active", notes="Rainfed block"),
        ]
        db.add_all(crops)
        db.flush()
        animals = [
            Livestock(farmer_id=farmer.id, farm_id=farm.id, animal_type="Cow", breed="Jersey cross", tag_id="COW-101", name="Lakshmi", sex="Female", date_of_birth=today - timedelta(days=4 * 365), weight=410, status="Healthy", notes="Milking"),
            Livestock(farmer_id=farmer.id, farm_id=farm.id, animal_type="Cow", breed="HF cross", tag_id="COW-102", name="Gauri", sex="Female", date_of_birth=today - timedelta(days=3 * 365), weight=430, status="Healthy"),
            Livestock(farmer_id=farmer.id, farm_id=farm.id, animal_type="Cow", breed="Kangayam", tag_id="COW-103", name="Nandini", sex="Female", date_of_birth=today - timedelta(days=5 * 365), weight=390, status="Healthy"),
            Livestock(farmer_id=farmer.id, farm_id=farm.id, animal_type="Goat", breed="Tellicherry", tag_id="GT-021", name="Meena", sex="Female", date_of_birth=today - timedelta(days=620), weight=34, status="Healthy"),
            Livestock(farmer_id=farmer.id, farm_id=farm.id, animal_type="Goat", breed="Tellicherry", tag_id="GT-022", name="Kannan", sex="Male", date_of_birth=today - timedelta(days=510), weight=38, status="Healthy"),
            Livestock(farmer_id=farmer.id, farm_id=farm.id, animal_type="Goat", breed="Boer cross", tag_id="GT-023", name="Malli", sex="Female", date_of_birth=today - timedelta(days=440), weight=31, status="Healthy"),
            Livestock(farmer_id=farmer.id, farm_id=farm.id, animal_type="Goat", breed="Kanni Adu", tag_id="GT-024", name="Selvi", sex="Female", date_of_birth=today - timedelta(days=700), weight=36, status="Healthy"),
        ]
        db.add_all(animals)
        db.flush()
        advice = {
            "condition": "Tomato Early Blight", "description": "A common fungal leaf disease with target-like spots.",
            "recommended_actions": ["Remove affected leaves", "Avoid overhead irrigation"],
            "preventive_measures": ["Rotate crops", "Keep tools clean"], "severity": "moderate",
            "urgency": "Action recommended within 24–48 hours", "confidence_label": "High confidence",
        }
        diagnosis = CropDiagnosis(
            farmer_id=farmer.id, farm_id=farm.id, crop_id=crops[0].id,
            image_path="data/demo/tomato_early_blight.jpg", predicted_class="Tomato___Early_blight",
            display_name="Tomato Early Blight", confidence=0.91, severity="moderate",
            advisory=json.dumps(advice), model_version="seed-demo-1.0",
            created_at=datetime.now() - timedelta(days=14), updated_at=datetime.now() - timedelta(days=14),
        )
        db.add(diagnosis)
        observation = LivestockObservation(
            livestock_id=animals[0].id, temperature=38.6, appetite="Normal", water_intake="Normal",
            activity_level="Normal", respiration="Normal", risk_score=0, risk_level="low",
            triggered_rules="[]", recommendations='["Continue routine observation."]',
            created_at=datetime.now() - timedelta(days=2), updated_at=datetime.now() - timedelta(days=2),
        )
        db.add(observation)
        records = [
            LivestockMedicalRecord(livestock_id=animals[0].id, record_type="Vaccination", title="FMD vaccination", description="Routine dose completed", date=today - timedelta(days=166), veterinarian="Dr. Priya"),
            LivestockMedicalRecord(livestock_id=animals[0].id, record_type="Veterinary visit", title="Routine health check", description="Healthy; body condition normal", date=today - timedelta(days=24), veterinarian="Dr. Priya"),
            LivestockMedicalRecord(livestock_id=animals[3].id, record_type="Deworming", title="Routine deworming", description="Completed under local animal-health worker guidance", date=today - timedelta(days=88)),
        ]
        db.add_all(records)
        vaccines = [
            VaccinationRecord(livestock_id=animals[0].id, vaccine_name="FMD Vaccination", administered_date=None, due_date=today + timedelta(days=5), status="Due Soon", notes="Confirm with veterinarian"),
            VaccinationRecord(livestock_id=animals[1].id, vaccine_name="HS Vaccination", administered_date=None, due_date=today + timedelta(days=34), status="Upcoming"),
            VaccinationRecord(livestock_id=animals[3].id, vaccine_name="Deworming", administered_date=today - timedelta(days=88), due_date=today - timedelta(days=88), status="Completed"),
        ]
        db.add_all(vaccines)
        alerts = [
            Alert(farmer_id=farmer.id, type="crop", severity="warning", title="Tomato Early Blight detected", message="Review the recommended actions and inspect nearby tomato plants.", related_entity="diagnosis", related_entity_id=None),
            Alert(farmer_id=farmer.id, type="vaccination", severity="reminder", title="FMD vaccination due soon", message="Lakshmi (COW-101) is due for vaccination in 5 days.", related_entity="livestock", related_entity_id=animals[0].id),
        ]
        db.add_all(alerts)
        db.commit()
        print("AgriVision AI demo data created.")
        print("Login: farmer@example.com / demo123")


if __name__ == "__main__":
    seed()

