from sqlalchemy import Column, Integer, String
from src.models.base import BaseModel
from src.database import db_session
from loguru import logger

class Option(BaseModel):
    """Model for storing application options"""
    __tablename__ = 'options'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)
    value = Column(String(200))

    DEFAULT_OPTIONS = {
        'demo_mode': 'false',
        'mqtt_broker': 'localhost',
        'mqtt_port': '1883',
        'mqtt_username': '',
        'mqtt_password': '',
        'iot_hub_connection_string': '',
        'telemetry_interval': '5000'
    }

    @classmethod
    def init_defaults(cls):
        """Initialize default options if they don't exist"""
        try:
            for name, default_value in cls.DEFAULT_OPTIONS.items():
                # Check if option exists
                option = db_session.query(cls).filter_by(name=name).first()
                if option is None:
                    # Create new option with default value
                    option = cls(name=name, value=default_value)
                    db_session.add(option)
            db_session.commit()
            logger.info("Default options initialized")
        except Exception as e:
            logger.error(f"Error initializing default options: {str(e)}")
            db_session.rollback()
            raise

    @classmethod
    def get_value(cls, name, default=None):
        """Get option value by name"""
        try:
            option = db_session.query(cls).filter_by(name=name).first()
            return option.value if option else default
        except Exception as e:
            logger.error(f"Error getting option value: {str(e)}")
            return default

    @classmethod
    def set_value(cls, name, value):
        """Set option value"""
        try:
            option = db_session.query(cls).filter_by(name=name).first()
            if option:
                option.value = str(value)
            else:
                option = cls(name=name, value=str(value))
                db_session.add(option)
            db_session.commit()
            logger.debug(f"Option {name} set to {value}")
        except Exception as e:
            logger.error(f"Error setting option value: {str(e)}")
            db_session.rollback()
            raise

    @classmethod
    def get_boolean(cls, name, default=False):
        """Get option value as boolean"""
        value = cls.get_value(name, str(default))
        return value.lower() == 'true'

    @classmethod
    def get_int(cls, name, default=0):
        """Get option value as integer"""
        try:
            return int(cls.get_value(name, default))
        except (ValueError, TypeError):
            return default

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