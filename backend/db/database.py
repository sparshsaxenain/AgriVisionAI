"""Database engine and session lifecycle."""
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    # Lightweight compatibility migration for databases created before farm
    # status became editable. New databases receive the column via metadata.
    if "status" not in {column["name"] for column in inspect(engine).get_columns("farms")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE farms ADD COLUMN status VARCHAR(40) NOT NULL DEFAULT 'Active'"))
