from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.api.deps import current_user
from backend.core.security import create_access_token, hash_password, verify_password
from backend.db.database import get_db
from backend.models import User
from backend.schemas.api import LoginRequest, TokenResponse, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    email = payload.email.strip().lower() if payload.email else None
    identity_match = User.phone == payload.phone.strip()
    if email:
        identity_match = or_(identity_match, User.email == email)
    existing = db.scalar(select(User).where(identity_match))
    if existing:
        raise HTTPException(status_code=409, detail="An account with this phone or email already exists.")
    user = User(
        **payload.model_dump(exclude={"password", "email", "phone"}),
        email=email,
        phone=payload.phone.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    identifier = payload.identifier.strip().lower()
    user = db.scalar(select(User).where(or_(User.email == identifier, User.phone == identifier)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email/phone or password.")
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
