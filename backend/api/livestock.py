from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.api.deps import current_user
from backend.db.database import get_db
from backend.models import Alert, Farm, Livestock, LivestockMedicalRecord, LivestockObservation, User, VaccinationRecord
from backend.schemas.api import (
    LivestockCreate, LivestockOut, LivestockUpdate, MedicalRecordCreate, MedicalRecordOut,
    ObservationCreate, ObservationOut, VaccinationCreate, VaccinationOut,
)
from backend.services.alert_service import create_health_alert
from backend.services.livestock_health import LivestockHealthEngine
from backend.services.vaccination_service import vaccination_status

router = APIRouter(prefix="/livestock", tags=["Livestock"])


def _animal(db: Session, user_id: int, animal_id: int) -> Livestock:
    animal = db.scalar(select(Livestock).where(Livestock.id == animal_id, Livestock.farmer_id == user_id))
    if not animal:
        raise HTTPException(404, "Animal not found.")
    return animal


@router.get("", response_model=list[LivestockOut])
def list_animals(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Livestock).where(Livestock.farmer_id == user.id).order_by(Livestock.animal_type, Livestock.name)).all()


@router.post("", response_model=LivestockOut, status_code=201)
def create_animal(payload: LivestockCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm = db.scalar(select(Farm).where(Farm.id == payload.farm_id, Farm.farmer_id == user.id))
    if not farm:
        raise HTTPException(404, "Farm not found.")
    animal = Livestock(farmer_id=user.id, **payload.model_dump())
    db.add(animal)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That animal tag is already in use.")
    db.refresh(animal)
    return animal


@router.get("/vaccinations/due")
def due_vaccinations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Return every pending vaccination across the signed-in farmer's livestock."""
    rows = db.execute(
        select(VaccinationRecord, Livestock)
        .join(Livestock, Livestock.id == VaccinationRecord.livestock_id)
        .where(Livestock.farmer_id == user.id, VaccinationRecord.administered_date.is_(None))
        .order_by(VaccinationRecord.due_date, Livestock.name, Livestock.tag_id)
    ).all()
    results = []
    changed = False
    for record, animal in rows:
        current = vaccination_status(record.due_date)
        if record.status != current:
            record.status = current
            changed = True
        results.append({
            "id": record.id,
            "animal_id": animal.id,
            "animal": animal.name or animal.tag_id,
            "tag_id": animal.tag_id,
            "animal_type": animal.animal_type,
            "vaccine_name": record.vaccine_name,
            "due_date": record.due_date.isoformat(),
            "status": current,
            "veterinarian": record.veterinarian,
            "notes": record.notes,
        })
    if changed:
        db.commit()
    return results


@router.get("/{animal_id}", response_model=LivestockOut)
def get_animal(animal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _animal(db, user.id, animal_id)


@router.put("/{animal_id}", response_model=LivestockOut)
def update_animal(animal_id: int, payload: LivestockCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    animal = _animal(db, user.id, animal_id)
    farm = db.scalar(select(Farm).where(Farm.id == payload.farm_id, Farm.farmer_id == user.id))
    if not farm:
        raise HTTPException(404, "Farm not found.")
    for key, value in payload.model_dump().items():
        setattr(animal, key, value)
    db.commit()
    db.refresh(animal)
    return animal


@router.patch("/{animal_id}", response_model=LivestockOut)
def patch_animal(animal_id: int, payload: LivestockUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    animal = _animal(db, user.id, animal_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(400, "Provide at least one animal property to update.")
    if "farm_id" in changes:
        farm = db.scalar(select(Farm).where(Farm.id == changes["farm_id"], Farm.farmer_id == user.id))
        if not farm:
            raise HTTPException(404, "Farm not found.")
    for key, value in changes.items():
        setattr(animal, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That animal tag is already in use.")
    db.refresh(animal)
    return animal


@router.delete("/{animal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_animal(
    animal_id: int,
    confirm_tag_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    animal = _animal(db, user.id, animal_id)
    if confirm_tag_id.strip().casefold() != animal.tag_id.strip().casefold():
        raise HTTPException(400, "Animal tag confirmation does not match.")
    db.execute(delete(Alert).where(
        Alert.farmer_id == user.id,
        Alert.related_entity == "livestock",
        Alert.related_entity_id == animal.id,
    ))
    db.delete(animal)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{animal_id}/observation", response_model=ObservationOut, status_code=201)
def add_observation(animal_id: int, payload: ObservationCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    animal = _animal(db, user.id, animal_id)
    risk = LivestockHealthEngine().evaluate(payload.model_dump())
    observation = LivestockObservation(
        livestock_id=animal.id, **payload.model_dump(), risk_score=risk["risk_score"],
        risk_level=risk["risk_level"], triggered_rules=json.dumps(risk["triggered_rules"]),
        recommendations=json.dumps(risk["recommendations"]),
    )
    animal.status = "Needs attention" if risk["risk_level"] in {"moderate", "high"} else "Healthy"
    if payload.weight:
        animal.weight = payload.weight
    db.add(observation)
    create_health_alert(db, animal, risk)
    db.commit()
    db.refresh(observation)
    return observation


@router.get("/{animal_id}/health-history", response_model=list[ObservationOut])
def health_history(animal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _animal(db, user.id, animal_id)
    return db.scalars(select(LivestockObservation).where(LivestockObservation.livestock_id == animal_id).order_by(LivestockObservation.created_at.desc())).all()


@router.post("/{animal_id}/medical-record", response_model=MedicalRecordOut, status_code=201)
def add_medical_record(animal_id: int, payload: MedicalRecordCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _animal(db, user.id, animal_id)
    record = LivestockMedicalRecord(livestock_id=animal_id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{animal_id}/medical-records", response_model=list[MedicalRecordOut])
def medical_records(animal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _animal(db, user.id, animal_id)
    return db.scalars(select(LivestockMedicalRecord).where(LivestockMedicalRecord.livestock_id == animal_id).order_by(LivestockMedicalRecord.date.desc())).all()


@router.post("/{animal_id}/vaccination", response_model=VaccinationOut, status_code=201)
def add_vaccination(animal_id: int, payload: VaccinationCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    animal = _animal(db, user.id, animal_id)
    values = payload.model_dump()
    values["status"] = "Completed" if payload.administered_date else vaccination_status(payload.due_date)
    record = VaccinationRecord(livestock_id=animal_id, **values)
    db.add(record)
    db.flush()
    if record.status in {"Due Soon", "Overdue"}:
        db.add(Alert(
            farmer_id=user.id,
            type="vaccination",
            severity="critical" if record.status == "Overdue" else "reminder",
            title=f"{record.vaccine_name} {record.status.lower()}",
            message=f"{record.vaccine_name} for {animal.name or animal.tag_id} is {record.status.lower()}.",
            related_entity="livestock",
            related_entity_id=animal.id,
        ))
    db.commit()
    db.refresh(record)
    return record


@router.get("/{animal_id}/vaccinations", response_model=list[VaccinationOut])
def vaccinations(animal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _animal(db, user.id, animal_id)
    records = db.scalars(select(VaccinationRecord).where(VaccinationRecord.livestock_id == animal_id).order_by(VaccinationRecord.due_date)).all()
    changed = False
    for record in records:
        if not record.administered_date:
            current = vaccination_status(record.due_date)
            if record.status != current:
                record.status = current
                changed = True
    if changed:
        db.commit()
    return records
