from sqlalchemy import Column, Integer, Float, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from src.models.base import BaseModel
from src.database import db_session
from src.utils.simulator import Simulator
import threading
from loguru import logger

class Sensor(BaseModel):
    """Model representing a sensor"""
    __tablename__ = 'sensors'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    base_value = Column(Float, nullable=False)
    unit = Column(Integer, nullable=False)
    variation_range = Column(Float, default=5.0)
    change_rate = Column(Float, default=0.5)
    interval = Column(Integer, default=2)
    error_definition = Column(Text)
    device_id = Column(Integer, ForeignKey('devices.id'))
    
    device = relationship("Device", back_populates="sensors")
    
    @classmethod
    def add(cls, name: str, base_value: float, unit: int, variation_range: float,
            change_rate: float, interval: int, error_definition: str = None, device_id: int = None) -> 'Sensor':
        """Add a new sensor"""
        sensor = cls(
            name=name,
            base_value=base_value,
            unit=unit,
            variation_range=variation_range,
            change_rate=change_rate,
            interval=interval,
            error_definition=error_definition,
            device_id=device_id
        )
        return sensor.save()
    
    @classmethod
    def get_all_by_ids(cls, list_of_ids):
        """Get all sensors with the given IDs"""
        return db_session.query(cls).filter(cls.id.in_(list_of_ids)).all()
    
    @classmethod
    def get_all_unassigned(cls):
        """Get all sensors that are not assigned to a device"""
        return db_session.query(cls).filter(cls.device_id == None).all()
    
    @classmethod
    def check_if_name_in_use(cls, name: str) -> bool:
        """Check if a sensor name is already in use"""
        return db_session.query(cls).filter(cls.name == name).first() is not None

    @classmethod
    def get_all(cls):
        '''Returns all sensors'''
        sensors = db_session.query(cls).all()
        logger.debug(f"Retrieved {len(sensors)} sensors")
        return sensors 