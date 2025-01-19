from sqlalchemy import Column, Integer, String
from models.base import BaseModel
from database import db_session
from loguru import logger

class Option(BaseModel):
    """Model representing a global option/setting"""
    __tablename__ = 'options'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    value = Column(String(255))
    
    @classmethod
    def get_value(cls, name: str) -> str:
        """Get the value of an option by name"""
        try:
            option = db_session.query(cls).filter(cls.name == name).first()
            value = option.value if option else None
            logger.debug(f"Retrieved value for option '{name}': {value}")
            return value
        except Exception as e:
            logger.error(f"Error getting value for option '{name}': {str(e)}")
            return None
    
    @classmethod
    def set_value(cls, name: str, value: str) -> bool:
        """Set the value of an option, creating it if it doesn't exist"""
        try:
            option = db_session.query(cls).filter(cls.name == name).first()
            if option:
                option.value = value
                logger.debug(f"Updated existing option '{name}' to: {value}")
            else:
                option = cls(name=name, value=value)
                db_session.add(option)
                logger.debug(f"Created new option '{name}' with value: {value}")
            
            db_session.commit()
            return True
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error setting option '{name}': {str(e)}")
            return False
    
    @classmethod
    def get_boolean(cls, name: str) -> bool:
        """Get a boolean option value"""
        value = cls.get_value(name)
        result = value == "1" if value is not None else False
        logger.debug(f"Retrieved boolean value for option '{name}': {result}")
        return result
    
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