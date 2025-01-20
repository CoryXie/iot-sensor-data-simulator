from sqlalchemy import Column, Integer, String, Boolean
from models.base import BaseModel
from database import db_session
from loguru import logger

class Option(BaseModel):
    """Model for storing application options"""
    __tablename__ = 'options'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)
    value = Column(String(200))

    @classmethod
    def init(cls):
        """Initialize default options"""
        try:
            # Set default options if they don't exist
            defaults = {
                'demo_mode': 'false'
            }
            
            for name, value in defaults.items():
                if not cls.get_value(name):
                    option = cls(name=name, value=value)
                    option.save()
                    logger.debug(f"Created default option: {name}={value}")
                    
        except Exception as e:
            logger.error(f"Error initializing options: {str(e)}")

    @classmethod
    def get_value(cls, name: str) -> str:
        """Get option value by name"""
        try:
            option = db_session.query(cls).filter_by(name=name).first()
            return option.value if option else None
        except Exception as e:
            logger.error(f"Error getting option value: {str(e)}")
            return None

    @classmethod
    def get_boolean(cls, name: str) -> bool:
        """Get boolean option value"""
        value = cls.get_value(name)
        return value.lower() == 'true' if value else False

    @classmethod
    def set_value(cls, name: str, value: str):
        """Set option value"""
        try:
            option = db_session.query(cls).filter_by(name=name).first()
            if option:
                option.value = str(value)
            else:
                option = cls(name=name, value=str(value))
            option.save()
        except Exception as e:
            logger.error(f"Error setting option value: {str(e)}")
    
    @classmethod
    def delete(cls, name: str) -> bool:
        """Delete an option by name"""
        try:
            option = db_session.query(cls).filter(cls.name == name).first()
            if option:
                db_session.delete(option)
                db_session.commit()
                logger.debug(f"Deleted option '{name}'")
                return True
            return False
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error deleting option '{name}': {str(e)}")
            return False 