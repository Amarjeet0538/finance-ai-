"""Database connection and lifecycle utilities for the Mock Finance Web App."""

import os
from collections.abc import Generator
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from finance_app.models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "finance.db"
DB_PATH = Path(os.environ.get("FINANCE_DB_PATH", str(DEFAULT_DB_PATH)))

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all database tables if they do not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def reset_db() -> None:
    """Drop all tables and recreate the schema."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency / generator providing a scoped database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
