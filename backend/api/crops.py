from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from backend.api.deps import current_user
from backend.core.config import get_settings
from backend.db.database import get_db
from backend.models import Alert, Crop, CropDiagnosis, Farm, User
from backend.schemas.api import CropCreate, CropOut, CropUpdate
from backend.services.crop_catalog import canonical_crop_type, supported_crop_types

router = APIRouter(prefix="/crops", tags=["Crops"])


def _owned_crop(db: Session, user_id: int, crop_id: int) -> Crop:
    crop = db.scalar(select(Crop).join(Farm).where(Crop.id == crop_id, Farm.farmer_id == user_id))
    if not crop:
        raise HTTPException(404, "Crop not found.")
    return crop


def _owned_farm(db: Session, user_id: int, farm_id: int) -> Farm:
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.farmer_id == user_id))
    if not farm:
        raise HTTPException(404, "Farm not found.")
    return farm


def _allowed_crop_name(value: str) -> str:
    canonical = canonical_crop_type(value)
    if canonical is None:
        choices = ", ".join(supported_crop_types())
        raise HTTPException(400, f"Unsupported crop type. Choose one of: {choices}.")
    return canonical


@router.get("", response_model=list[CropOut])
def list_crops(farm_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Crop).join(Farm).where(Farm.farmer_id == user.id)
    if farm_id:
        query = query.where(Crop.farm_id == farm_id)
    return db.scalars(query.order_by(Crop.created_at.desc())).all()


@router.post("", response_model=CropOut, status_code=201)
def create_crop(payload: CropCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _owned_farm(db, user.id, payload.farm_id)
    values = payload.model_dump()
    values["crop_name"] = _allowed_crop_name(payload.crop_name)
    crop = Crop(**values)
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return crop


@router.get("/{crop_id}", response_model=CropOut)
def get_crop(crop_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _owned_crop(db, user.id, crop_id)


@router.patch("/{crop_id}", response_model=CropOut)
def patch_crop(
    crop_id: int,
    payload: CropUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    crop = _owned_crop(db, user.id, crop_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(400, "Provide at least one crop-cycle property to update.")
    required = {"farm_id", "crop_name", "variety", "area", "crop_stage", "status", "notes"}
    if any(changes.get(field) is None for field in required & changes.keys()):
        raise HTTPException(400, "Required crop-cycle properties cannot be null.")
    if "farm_id" in changes:
        _owned_farm(db, user.id, changes["farm_id"])
        if changes["farm_id"] != crop.farm_id:
            db.execute(
                update(CropDiagnosis)
                .where(CropDiagnosis.crop_id == crop.id)
                .values(farm_id=changes["farm_id"])
            )
    if "crop_name" in changes:
        changes["crop_name"] = _allowed_crop_name(changes["crop_name"])
    for key, value in changes.items():
        setattr(crop, key, value)
    db.commit()
    db.refresh(crop)
    return crop


@router.delete("/{crop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_crop(
    crop_id: int,
    confirm_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    crop = _owned_crop(db, user.id, crop_id)
    if confirm_name.strip().casefold() != crop.crop_name.strip().casefold():
        raise HTTPException(400, "Crop name confirmation does not match.")

    diagnoses = list(db.scalars(select(CropDiagnosis).where(CropDiagnosis.crop_id == crop.id)).all())
    diagnosis_ids = [item.id for item in diagnoses]
    alert_conditions = [(Alert.related_entity == "crop") & (Alert.related_entity_id == crop.id)]
    if diagnosis_ids:
        alert_conditions.append((Alert.related_entity == "diagnosis") & Alert.related_entity_id.in_(diagnosis_ids))
    db.execute(delete(Alert).where(Alert.farmer_id == user.id, or_(*alert_conditions)))

    image_paths = [Path(item.image_path) for item in diagnoses if item.image_path]
    db.delete(crop)
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
