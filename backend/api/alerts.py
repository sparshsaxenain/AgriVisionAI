from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import current_user
from backend.db.database import get_db
from backend.models import Alert, User
from backend.schemas.api import AlertOut

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(include_read: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Alert).where(Alert.farmer_id == user.id)
    if not include_read:
        query = query.where(Alert.is_read.is_(False))
    return db.scalars(query.order_by(Alert.created_at.desc())).all()


@router.patch("/{alert_id}/read", response_model=AlertOut)
def mark_read(alert_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    alert = db.scalar(select(Alert).where(Alert.id == alert_id, Alert.farmer_id == user.id))
    if not alert:
        raise HTTPException(404, "Alert not found.")
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert

