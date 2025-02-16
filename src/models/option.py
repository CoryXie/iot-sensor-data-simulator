from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Mapped
from typing import Optional
from datetime import datetime
from src.database.base import Base
from src.models.base_model import BaseModel
from src.database import SessionLocal
from src.database import db_session
from loguru import logger

class Option(BaseModel):
    """Model for storing application options/settings"""
    __tablename__ = 'options'

    id: Mapped[int] = Column(Integer, primary_key=True)
    name: Mapped[str] = Column(String(100), nullable=False, unique=True)
    value: Mapped[str] = Column(String(500))
    created_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, name: str, value: str):
        """Initialize an option
        
        Args:
            name: Option name
            value: Option value
        """
        super().__init__()
        self.name = name
        self.value = value

    @classmethod
    def get_value(cls, name: str, default: str = None) -> str:
        """Get an option value by name"""
        try:
            with SessionLocal() as session:
                option = session.query(cls).filter_by(name=name).first()
                return option.value if option else default
        except Exception as e:
            logger.error(f"Error getting option value: {str(e)}")
            return default

    @classmethod
    def set_value(cls, name, value):
        """Set an option value safely within a transaction"""
        from src.database.database import SessionLocal
        session = SessionLocal()
        
        try:
            option = session.query(cls).filter_by(name=name).first()
            if not option:
                option = cls(name=name, value=value)
                session.add(option)
            else:
                option.value = value
            
            session.commit()
            logger.info(f"Option '{name}' set to '{value}'")
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting option value: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def delete_option(cls, name: str) -> bool:
        """Delete an option by name"""
        try:
            session = db_session()
            option = session.query(cls).filter_by(name=name).first()
            if option:
                session.delete(option)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting option: {str(e)}")
            return False
        finally:
            session.close()

    def __repr__(self):
        return f"<Option {self.name}={self.value}>" 