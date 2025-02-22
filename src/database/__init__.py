# Initialize database package
from .base import Base
from .database import (
    SessionLocal, get_db,
    init_db, check_schema,
    ensure_database, engine,
    db_session  # This is the proper context manager
)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Use PostgreSQL UUID extension
DATABASE_URL = f"sqlite:///{os.path.join(os.getcwd(), 'data', 'simulation.db')}"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

__all__ = [
    'Base', 'SessionLocal', 'get_db',
    'init_db', 'check_schema',
    'ensure_database', 'engine',
    'db_session'  # Now references the real context manager
] 