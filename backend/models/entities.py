"""SQLAlchemy persistence models for crop and livestock workflows."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(180), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    village: Mapped[str] = mapped_column(String(120), default="")
    district: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    farms: Mapped[list[Farm]] = relationship(back_populates="farmer", cascade="all, delete-orphan")
    livestock: Mapped[list[Livestock]] = relationship(back_populates="farmer", cascade="all, delete-orphan")


class Farm(Base, TimestampMixin):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    farm_name: Mapped[str] = mapped_column(String(160))
    village: Mapped[str] = mapped_column(String(120), default="")
    district: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_area: Mapped[float] = mapped_column(Float, default=0)
    area_unit: Mapped[str] = mapped_column(String(30), default="acres")
    soil_type: Mapped[str] = mapped_column(String(80), default="Unknown")
    irrigation_type: Mapped[str] = mapped_column(String(80), default="Rainfed")
    status: Mapped[str] = mapped_column(String(40), default="Active")
    farmer: Mapped[User] = relationship(back_populates="farms")
    crops: Mapped[list[Crop]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    livestock: Mapped[list[Livestock]] = relationship(back_populates="farm", cascade="all, delete-orphan")


class Crop(Base, TimestampMixin):
    __tablename__ = "crops"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    crop_name: Mapped[str] = mapped_column(String(100))
    variety: Mapped[str] = mapped_column(String(100), default="")
    sowing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_harvest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    area: Mapped[float] = mapped_column(Float, default=0)
    crop_stage: Mapped[str] = mapped_column(String(40), default="Seedling")
    status: Mapped[str] = mapped_column(String(30), default="Active")
    notes: Mapped[str] = mapped_column(Text, default="")
    farm: Mapped[Farm] = relationship(back_populates="crops")
    diagnoses: Mapped[list[CropDiagnosis]] = relationship(back_populates="crop", cascade="all, delete-orphan")


class CropDiagnosis(Base, TimestampMixin):
    __tablename__ = "crop_diagnoses"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"), index=True)
    image_path: Mapped[str] = mapped_column(String(500), default="")
    predicted_class: Mapped[str] = mapped_column(String(180))
    display_name: Mapped[str] = mapped_column(String(180))
    confidence: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(30))
    advisory: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(100), default="unknown")
    crop: Mapped[Crop] = relationship(back_populates="diagnoses")
    farm: Mapped[Farm] = relationship()


class Livestock(Base, TimestampMixin):
    __tablename__ = "livestock"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    animal_type: Mapped[str] = mapped_column(String(40))
    breed: Mapped[str] = mapped_column(String(100), default="")
    tag_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    sex: Mapped[str] = mapped_column(String(20), default="Unknown")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Healthy")
    notes: Mapped[str] = mapped_column(Text, default="")
    farmer: Mapped[User] = relationship(back_populates="livestock")
    farm: Mapped[Farm] = relationship(back_populates="livestock")
    observations: Mapped[list[LivestockObservation]] = relationship(back_populates="livestock", cascade="all, delete-orphan")
    medical_records: Mapped[list[LivestockMedicalRecord]] = relationship(back_populates="livestock", cascade="all, delete-orphan")
    vaccinations: Mapped[list[VaccinationRecord]] = relationship(back_populates="livestock", cascade="all, delete-orphan")


class LivestockObservation(Base, TimestampMixin):
    __tablename__ = "livestock_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    livestock_id: Mapped[int] = mapped_column(ForeignKey("livestock.id"), index=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    appetite: Mapped[str] = mapped_column(String(30), default="Normal")
    water_intake: Mapped[str] = mapped_column(String(30), default="Normal")
    activity_level: Mapped[str] = mapped_column(String(30), default="Normal")
    milk_production: Mapped[float | None] = mapped_column(Float, nullable=True)
    respiration: Mapped[str] = mapped_column(String(30), default="Normal")
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    visible_injury: Mapped[bool] = mapped_column(Boolean, default=False)
    diarrhea: Mapped[bool] = mapped_column(Boolean, default=False)
    coughing: Mapped[bool] = mapped_column(Boolean, default=False)
    nasal_discharge: Mapped[bool] = mapped_column(Boolean, default=False)
    pregnancy_status: Mapped[str] = mapped_column(String(40), default="Not applicable")
    notes: Mapped[str] = mapped_column(Text, default="")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    triggered_rules: Mapped[str] = mapped_column(Text, default="[]")
    recommendations: Mapped[str] = mapped_column(Text, default="[]")
    livestock: Mapped[Livestock] = relationship(back_populates="observations")


class LivestockMedicalRecord(Base, TimestampMixin):
    __tablename__ = "livestock_medical_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    livestock_id: Mapped[int] = mapped_column(ForeignKey("livestock.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[date] = mapped_column(Date)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    veterinarian: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    livestock: Mapped[Livestock] = relationship(back_populates="medical_records")


class VaccinationRecord(Base, TimestampMixin):
    __tablename__ = "vaccination_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    livestock_id: Mapped[int] = mapped_column(ForeignKey("livestock.id"), index=True)
    vaccine_name: Mapped[str] = mapped_column(String(160))
    administered_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="Upcoming")
    veterinarian: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    livestock: Mapped[Livestock] = relationship(back_populates="vaccinations")


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    related_entity: Mapped[str] = mapped_column(String(50), default="")
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
