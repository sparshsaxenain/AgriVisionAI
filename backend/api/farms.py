from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import current_user
from backend.db.database import get_db
from backend.models import Farm, User
from backend.schemas.api import FarmCreate, FarmOut

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

