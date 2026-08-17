"""Pydantic API contracts."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    email: str | None = None
    password: str = Field(min_length=6, max_length=128)
    preferred_language: str = "en"
    village: str = ""
    district: str = ""
    state: str = ""


class LoginRequest(BaseModel):
    identifier: str
    password: str


class UserOut(ORMModel):
    id: int
    name: str
    phone: str
    email: str | None
    preferred_language: str
    village: str
    district: str
    state: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FarmCreate(BaseModel):
    farm_name: str = Field(min_length=2, max_length=160)
    village: str = ""
    district: str = ""
    state: str = ""
    latitude: float | None = None
    longitude: float | None = None
    total_area: float = Field(default=0, ge=0)
    area_unit: str = "acres"
    soil_type: str = "Unknown"
    irrigation_type: str = "Rainfed"
    status: str = Field(default="Active", max_length=40)


class FarmUpdate(BaseModel):
    farm_name: str | None = Field(default=None, min_length=2, max_length=160)
    village: str | None = None
    district: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    total_area: float | None = Field(default=None, ge=0)
    area_unit: str | None = None
    soil_type: str | None = None
    irrigation_type: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=40)


class FarmOut(ORMModel):
    id: int
    farmer_id: int
    farm_name: str
    village: str
    district: str
    state: str
    latitude: float | None
    longitude: float | None
    total_area: float
    area_unit: str
    soil_type: str
    irrigation_type: str
    status: str
    created_at: datetime


class CropCreate(BaseModel):
    farm_id: int
    crop_name: str = Field(min_length=2, max_length=100)
    variety: str = Field(default="", max_length=100)
    sowing_date: date | None = None
    expected_harvest_date: date | None = None
    area: float = Field(default=0, ge=0)
    crop_stage: str = "Seedling"
    status: str = "Active"
    notes: str = ""


class CropUpdate(BaseModel):
    farm_id: int | None = None
    crop_name: str | None = Field(default=None, min_length=2, max_length=100)
    variety: str | None = Field(default=None, max_length=100)
    sowing_date: date | None = None
    expected_harvest_date: date | None = None
    area: float | None = Field(default=None, ge=0)
    crop_stage: str | None = Field(default=None, min_length=1, max_length=40)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    notes: str | None = None


class CropOut(ORMModel):
    id: int
    farm_id: int
    crop_name: str
    variety: str
    sowing_date: date | None
    expected_harvest_date: date | None
    area: float
    crop_stage: str
    status: str
    notes: str
    created_at: datetime


class PredictionItem(BaseModel):
    class_name: str
    display_name: str
    confidence: float


class DiagnosisPreview(BaseModel):
    predicted_class: str
    display_name: str
    confidence: float
    confidence_label: str
    top_predictions: list[PredictionItem]
    model_version: str
    inference_time_ms: float
    severity: str
    advisory: dict[str, Any]
    image_token: str
    mock_mode: bool = False
    is_ood: bool = False
    ood_reason: str = ""


class DiagnosisSave(BaseModel):
    farm_id: int
    crop_id: int
    image_token: str
    predicted_class: str
    display_name: str
    confidence: float = Field(ge=0, le=1)
    severity: str
    advisory: dict[str, Any]
    model_version: str = "unknown"


class DiagnosisOut(ORMModel):
    id: int
    farmer_id: int
    farm_id: int
    crop_id: int
    image_path: str
    predicted_class: str
    display_name: str
    confidence: float
    severity: str
    advisory: str
    model_version: str
    created_at: datetime


class LivestockCreate(BaseModel):
    farm_id: int
    animal_type: str
    breed: str = ""
    tag_id: str = Field(min_length=2, max_length=80)
    name: str = ""
    sex: str = "Unknown"
    date_of_birth: date | None = None
    weight: float | None = Field(default=None, ge=0)
    status: str = "Healthy"
    notes: str = ""


class LivestockUpdate(BaseModel):
    farm_id: int | None = None
    animal_type: str | None = None
    breed: str | None = None
    tag_id: str | None = Field(default=None, min_length=2, max_length=80)
    name: str | None = None
    sex: str | None = None
    date_of_birth: date | None = None
    weight: float | None = Field(default=None, ge=0)
    status: str | None = None
    notes: str | None = None


class LivestockOut(ORMModel):
    id: int
    farmer_id: int
    farm_id: int
    animal_type: str
    breed: str
    tag_id: str
    name: str
    sex: str
    date_of_birth: date | None
    weight: float | None
    status: str
    notes: str
    created_at: datetime


class ObservationCreate(BaseModel):
    temperature: float | None = Field(default=None, ge=30, le=45)
    appetite: str = "Normal"
    water_intake: str = "Normal"
    activity_level: str = "Normal"
    milk_production: float | None = Field(default=None, ge=0)
    respiration: str = "Normal"
    weight: float | None = Field(default=None, ge=0)
    visible_injury: bool = False
    diarrhea: bool = False
    coughing: bool = False
    nasal_discharge: bool = False
    pregnancy_status: str = "Not applicable"
    notes: str = ""


class ObservationOut(ORMModel):
    id: int
    livestock_id: int
    temperature: float | None
    appetite: str
    activity_level: str
    risk_score: int
    risk_level: str
    triggered_rules: str
    recommendations: str
    created_at: datetime


class MedicalRecordCreate(BaseModel):
    record_type: str
    title: str = Field(min_length=2, max_length=180)
    description: str = ""
    date: date
    next_due_date: date | None = None
    veterinarian: str = ""
    notes: str = ""


class MedicalRecordOut(ORMModel):
    id: int
    livestock_id: int
    record_type: str
    title: str
    description: str
    date: date
    next_due_date: date | None
    veterinarian: str
    notes: str


class VaccinationCreate(BaseModel):
    vaccine_name: str = Field(min_length=2, max_length=160)
    administered_date: date | None = None
    due_date: date
    status: str = "Upcoming"
    veterinarian: str = ""
    notes: str = ""


class VaccinationOut(ORMModel):
    id: int
    livestock_id: int
    vaccine_name: str
    administered_date: date | None
    due_date: date
    status: str
    veterinarian: str
    notes: str


class AlertOut(ORMModel):
    id: int
    farmer_id: int
    type: str
    severity: str
    title: str
    message: str
    related_entity: str
    related_entity_id: int | None
    is_read: bool
    created_at: datetime
