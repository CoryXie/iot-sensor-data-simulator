from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from models.base import BaseModel
from database import db_session
from utils.iot_hub_helper import IoTHubHelper
from loguru import logger

class Device(BaseModel):
    """Model representing a device"""
    __tablename__ = 'devices'
    
    id = Column(Integer, primary_key=True)
    device_name = Column(String(100), nullable=False)
    container_id = Column(Integer, ForeignKey('containers.id'))
    
    container = relationship("Container", back_populates="devices")
    sensors = relationship("Sensor", back_populates="device", cascade="all, delete-orphan")
    
    @classmethod
    def add(cls, device_name: str, container_id: int = None) -> 'Device':
        """Add a new device"""
        device = cls(
            device_name=device_name,
            container_id=container_id
        )
        return device.save()
    
    @property
    def name(self):
        """Get the device name"""
        return self.device_name
    
    @classmethod
    def check_if_name_in_use(cls, name: str) -> bool:
        """Check if a device name is already in use"""
        return db_session.query(cls).filter(cls.device_name == name).first() is not None 

    @classmethod
    def get_all(cls):
        '''Returns all devices'''
        devices = db_session.query(cls).all()
        logger.debug(f"Retrieved {len(devices)} devices")
        return devices 