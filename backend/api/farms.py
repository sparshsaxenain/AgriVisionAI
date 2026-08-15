from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from backend.api.deps import current_user
from backend.core.config import get_settings
from backend.db.database import get_db
from backend.models import Alert, Crop, CropDiagnosis, Farm, Livestock, User
from backend.schemas.api import FarmCreate, FarmOut, FarmUpdate

router = APIRouter(prefix="/farms", tags=["Farms"])


@router.get("", response_model=list[FarmOut])
def list_farms(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Farm).where(Farm.farmer_id == user.id).order_by(Farm.created_at)).all()


@router.post("", response_model=FarmOut, status_code=201)
def create_farm(payload: FarmCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm = Farm(farmer_id=user.id, **payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@router.get("/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.farmer_id == user.id))
    if not farm:
        raise HTTPException(404, "Farm not found.")
    return farm


@router.put("/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: int, payload: FarmCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.farmer_id == user.id))
    if not farm:
        raise HTTPException(404, "Farm not found.")
    for key, value in payload.model_dump().items():
        setattr(farm, key, value)
    db.commit()
    db.refresh(farm)
    return farm


@router.patch("/{farm_id}", response_model=FarmOut)
def patch_farm(farm_id: int, payload: FarmUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.farmer_id == user.id))
    if not farm:
        raise HTTPException(404, "Farm not found.")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(400, "Provide at least one farm property to update.")
    for key, value in changes.items():
        setattr(farm, key, value)
    db.commit()
    db.refresh(farm)
    return farm


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(
    farm_id: int,
    confirm_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.farmer_id == user.id))
    if not farm:
        raise HTTPException(404, "Farm not found.")
    if confirm_name.strip().casefold() != farm.farm_name.strip().casefold():
        raise HTTPException(400, "Farm name confirmation does not match.")

    crop_ids = list(db.scalars(select(Crop.id).where(Crop.farm_id == farm.id)).all())
    diagnosis_rows = list(db.scalars(select(CropDiagnosis).where(CropDiagnosis.farm_id == farm.id)).all())
    diagnosis_ids = [item.id for item in diagnosis_rows]
    animal_ids = list(db.scalars(select(Livestock.id).where(Livestock.farm_id == farm.id)).all())
    alert_conditions = []
    if animal_ids:
        alert_conditions.append((Alert.related_entity == "livestock") & Alert.related_entity_id.in_(animal_ids))
    if diagnosis_ids:
        alert_conditions.append((Alert.related_entity == "diagnosis") & Alert.related_entity_id.in_(diagnosis_ids))
    if crop_ids:
        alert_conditions.append((Alert.related_entity == "crop") & Alert.related_entity_id.in_(crop_ids))
    if alert_conditions:
        db.execute(delete(Alert).where(Alert.farmer_id == user.id, or_(*alert_conditions)))

    image_paths = [Path(item.image_path) for item in diagnosis_rows if item.image_path]
    db.delete(farm)
    db.commit()

    uploads_dir = get_settings().uploads_dir.resolve()
    for image_path in image_paths:
        try:
            resolved = image_path.resolve()
            if resolved.is_relative_to(uploads_dir):
                resolved.unlink(missing_ok=True)
        except OSError:
            pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)
