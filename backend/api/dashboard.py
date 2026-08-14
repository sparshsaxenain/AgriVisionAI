from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.deps import current_user
from backend.db.database import get_db
from backend.models import Alert, Crop, CropDiagnosis, Farm, Livestock, LivestockObservation, User, VaccinationRecord
from backend.services.vaccination_service import due_text, vaccination_status

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm_ids = select(Farm.id).where(Farm.farmer_id == user.id)
    farms = db.scalar(select(func.count()).select_from(Farm).where(Farm.farmer_id == user.id)) or 0
    active_crops = db.scalar(select(func.count()).select_from(Crop).where(Crop.farm_id.in_(farm_ids), Crop.status == "Active")) or 0
    livestock_count = db.scalar(select(func.count()).select_from(Livestock).where(Livestock.farmer_id == user.id)) or 0
    diagnoses_count = db.scalar(select(func.count()).select_from(CropDiagnosis).where(CropDiagnosis.farmer_id == user.id)) or 0
    active_alerts = db.scalar(select(func.count()).select_from(Alert).where(Alert.farmer_id == user.id, Alert.is_read.is_(False))) or 0
    diagnoses = db.execute(
        select(CropDiagnosis, Crop.crop_name, Farm.farm_name).join(Crop, Crop.id == CropDiagnosis.crop_id).join(Farm, Farm.id == CropDiagnosis.farm_id)
        .where(CropDiagnosis.farmer_id == user.id).order_by(CropDiagnosis.created_at.desc()).limit(8)
    ).all()
    animals = db.scalars(select(Livestock).where(Livestock.farmer_id == user.id)).all()
    animal_ids = [a.id for a in animals]
    vaccines = db.execute(
        select(VaccinationRecord, Livestock.name, Livestock.tag_id, Livestock.animal_type)
        .join(Livestock).where(Livestock.farmer_id == user.id, VaccinationRecord.administered_date.is_(None))
        .order_by(VaccinationRecord.due_date).limit(8)
    ).all()
    alerts = db.scalars(select(Alert).where(Alert.farmer_id == user.id, Alert.is_read.is_(False)).order_by(Alert.created_at.desc()).limit(8)).all()
    crop_distribution = db.execute(select(Crop.crop_name, func.count(Crop.id)).where(Crop.farm_id.in_(farm_ids), Crop.status == "Active").group_by(Crop.crop_name)).all()
    animal_distribution = db.execute(select(Livestock.animal_type, func.count(Livestock.id)).where(Livestock.farmer_id == user.id).group_by(Livestock.animal_type)).all()
    risk_rows = db.execute(
        select(LivestockObservation.risk_level, func.count(LivestockObservation.id))
        .join(Livestock).where(Livestock.farmer_id == user.id).group_by(LivestockObservation.risk_level)
    ).all()
    return {
        "kpis": {"farms": farms, "active_crops": active_crops, "livestock": livestock_count, "diagnoses": diagnoses_count, "active_alerts": active_alerts},
        "recent_diagnoses": [{"id": d.id, "date": d.created_at.isoformat(), "crop": crop, "farm": farm, "condition": d.display_name, "confidence": d.confidence, "severity": d.severity} for d, crop, farm in diagnoses],
        "upcoming_vaccinations": [{"id": v.id, "animal": name or tag, "tag_id": tag, "animal_type": animal_type, "task": v.vaccine_name, "due_date": v.due_date.isoformat(), "status": vaccination_status(v.due_date), "due_text": due_text(v.due_date)} for v, name, tag, animal_type in vaccines],
        "alerts": [{"id": a.id, "severity": a.severity, "title": a.title, "message": a.message, "created_at": a.created_at.isoformat()} for a in alerts],
        "crop_distribution": [{"name": name, "count": count} for name, count in crop_distribution],
        "livestock_distribution": [{"name": name, "count": count} for name, count in animal_distribution],
        "health_risk_distribution": [{"name": name.title(), "count": count} for name, count in risk_rows],
    }

