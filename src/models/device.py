from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship, Mapped, joinedload
from src.database import Base, SessionLocal
from src.utils.iot_hub_helper import IoTHubHelper
from loguru import logger
from src.models.base_model import BaseModel
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from src.models.container import Container
    from src.models.sensor import Sensor
    from src.models.room import Room

class Device(BaseModel):
    """Device model for smart home devices"""
    __tablename__ = 'devices'
    __table_args__ = {'extend_existing': True}
    
    id: Mapped[int] = Column(Integer, primary_key=True)
    name = Column(String(100))
    type = Column(String(50))
    description: Mapped[Optional[str]] = Column(String(200))
    location: Mapped[Optional[str]] = Column(String(50))
    icon: Mapped[Optional[str]] = Column(String(50), default='devices')
    container_id: Mapped[int] = Column(Integer, ForeignKey('containers.id'))
    is_active: Mapped[bool] = Column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    room_id = Column(Integer, ForeignKey('rooms.id'))
    
    # Relationships
    container: Mapped[Optional["Container"]] = relationship(
        "Container", 
        back_populates="devices",
        foreign_keys=[container_id]
    )
    room = relationship("Room", back_populates="devices")
    sensors = relationship(
        "Sensor", 
        back_populates="device", 
        cascade="all, delete-orphan",
        lazy="joined"
    )
    
    def __init__(self, name: str, type: str, description: str = None, location: str = None, 
                 icon: str = None, room: 'Room' = None, container: 'Container' = None):
        """Initialize a device with required fields"""
        super().__init__()
        self.name = name
        self.type = type
        self.description = description
        self.location = location
        self.icon = icon
        self.room = room
        self.container = container
        # Set default values for other fields
        self.is_active = False

    def add_sensor(self, sensor):
        """Add a sensor to this device"""
        try:
            with SessionLocal() as session:
                self.sensors.append(sensor)
                session.add(self)
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding sensor to device: {str(e)}")
            return False

    def remove_sensor(self, sensor):
        """Remove a sensor from this device"""
        try:
            with SessionLocal() as session:
                self.sensors.remove(sensor)
                session.add(self)
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error removing sensor from device: {str(e)}")
            return False

    def get_sensors(self):
        """Get all sensors for this device"""
        try:
            return self.sensors
        except Exception as e:
            logger.error(f"Error getting device sensors: {str(e)}")
            return []

    @classmethod
    def get_by_container(cls, container_id: int):
        """Get all devices in a container"""
        try:
            session = SessionLocal()
            return session.query(cls).filter_by(container_id=container_id).all()
        except Exception as e:
            logger.error(f"Error getting devices by container: {str(e)}")
            return []

    @classmethod
    def get_by_name(cls, name: str) -> Optional['Device']:
        """Get a device by its name"""
        try:
            with SessionLocal() as session:
                return session.query(cls).filter_by(name=name).first()
        except Exception as e:
            logger.error(f"Error getting device by name {name}: {str(e)}")
            return None

    @classmethod
    def get_all(cls) -> List["Device"]:
        """Get all devices"""
        try:
            with SessionLocal() as session:
                return session.query(cls).options(
                    joinedload(cls.container)  # Eager load container relationship
                ).all()
        except Exception as e:
            logger.error(f"Error getting all devices: {str(e)}")
            return []

    @classmethod
    def add(cls, name: str, type: str, location: str, container_id: Optional[int] = None) -> 'Device':
        """Add a new device"""
        try:
            session = SessionLocal()
            device = cls(
                name=name,
                type=type,
                location=location,
                container_id=container_id
            )
            session.add(device)
            session.commit()
            return device
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding device: {str(e)}")
            raise

    def __repr__(self):
        return f"<Device(name='{self.name}', type='{self.type}', location='{self.location}')>"

    def activate(self):
        """Activate the device and its sensors"""
        self.is_active = True
        for sensor in self.sensors:
            sensor.is_active = True
        self.updated_at = datetime.utcnow()

    def deactivate(self):
        """Deactivate the device and its sensors"""
        self.is_active = False 
        for sensor in self.sensors:
            sensor.is_active = False
        self.updated_at = datetime.utcnow()