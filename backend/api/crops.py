from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import current_user
from backend.db.database import get_db
from backend.models import Crop, Farm, User
from backend.schemas.api import CropCreate, CropOut

router = APIRouter(prefix="/crops", tags=["Crops"])


@router.get("", response_model=list[CropOut])
def list_crops(farm_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Crop).join(Farm).where(Farm.farmer_id == user.id)
    if farm_id:
        query = query.where(Crop.farm_id == farm_id)
    return db.scalars(query.order_by(Crop.created_at.desc())).all()


@router.post("", response_model=CropOut, status_code=201)
def create_crop(payload: CropCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm = db.scalar(select(Farm).where(Farm.id == payload.farm_id, Farm.farmer_id == user.id))
    if not farm:
        raise HTTPException(404, "Farm not found.")
    crop = Crop(**payload.model_dump())
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return crop


@router.get("/{crop_id}", response_model=CropOut)
def get_crop(crop_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    crop = db.scalar(select(Crop).join(Farm).where(Crop.id == crop_id, Farm.farmer_id == user.id))
    if not crop:
        raise HTTPException(404, "Crop not found.")
    return crop

