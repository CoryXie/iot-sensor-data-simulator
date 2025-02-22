from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.device import Device
    from src.models.room import Room

from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped, joinedload
from datetime import datetime
from src.models.base_model import BaseModel
from src.database import db_session
from loguru import logger
import random
import time
from sqlalchemy import event
import uuid
from src.database import SessionLocal
from src.models.device import Device
from src.models.container import Container

class Sensor(BaseModel):
    """Model for sensors attached to devices"""
    __tablename__ = 'sensors'
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = Column(Integer, primary_key=True)
    name: Mapped[str] = Column(String(100), nullable=False)
    type: Mapped[str] = Column(String(50))
    unit: Mapped[str] = Column(String(20))
    min_value: Mapped[float] = Column(Float)
    max_value: Mapped[float] = Column(Float)
    _current_value_db: Mapped[float] = Column('current_value', Float)
    base_value: Mapped[float] = Column(Float)
    variation_range: Mapped[float] = Column(Float, default=1.0)
    change_rate: Mapped[float] = Column(Float, default=0.1)
    interval: Mapped[int] = Column(Integer, default=5)
    device_id: Mapped[int] = Column(Integer, ForeignKey('devices.id'))
    error_definition: Mapped[Optional[str]] = Column(String(200))
    created_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    room_id: Mapped[int] = Column(Integer, ForeignKey('rooms.id'))
    icon: Mapped[Optional[str]] = Column(String(50))
    container_id: Mapped[int] = Column(Integer, ForeignKey('containers.id'))

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="sensors")
    room: Mapped["Room"] = relationship("Room", back_populates="sensors", overlaps="sensors")
    container: Mapped["Container"] = relationship("Container", back_populates="sensors")

    @property
    def current_value(self):
        """Get the current value with validation"""
        value = self._current_value_db
        if value is None:
            return self.min_value
        return max(self.min_value, min(self.max_value, value))

    @current_value.setter
    def current_value(self, value):
        """Set the current value with validation"""
        if value is not None:
            validated_value = max(self.min_value, min(self.max_value, value))
            self._current_value_db = validated_value
        else:
            self._current_value_db = self.min_value

    def __init__(self, name: str, type: str, unit: str = None, 
                 device: Device = None, room: Room = None, 
                 container: Container = None, **kwargs):
        """Initialize a sensor with optional relationships"""
        # Filter out BaseModel parameters first
        base_model_args = {k: v for k, v in kwargs.items() 
                          if k in ['created_at', 'updated_at', 'description']}
        super().__init__(**base_model_args)
        
        # Set direct fields
        self.name = name
        self.type = type
        self.unit = unit
        self.device = device
        self.room = room
        self.container = container
        
        # Set sensor-specific fields with defaults
        self.min_value = kwargs.pop('min_value', 0)
        self.max_value = kwargs.pop('max_value', 100)
        self.variation_range = kwargs.pop('variation_range', 1.0)
        self.change_rate = kwargs.pop('change_rate', 0.1)
        self.interval = kwargs.pop('interval', 5)
        
        # Initialize calculated fields
        self.current_value = (self.min_value + self.max_value) / 2
        self.base_value = self.current_value
        
        # Handle any remaining unexpected arguments
        if kwargs:
            logger.warning(f"Unexpected arguments in Sensor init: {', '.join(kwargs.keys())}")

    def get_simulator(self):
        """Get or create the simulator instance"""
        if self._simulator is None:
            from src.utils.simulator import Simulator
            self._simulator = Simulator(self)
        return self._simulator

    def update_value(self, value: float, session=None) -> bool:
        """Update the sensor's current value"""
        try:
            logger.debug(f"[Sensor {self.id}] Update initiated - Current: {self.current_value}, New: {value}")
            
            if value < self.min_value or value > self.max_value:
                logger.warning(f"[Sensor {self.id}] Value {value} outside range [{self.min_value}, {self.max_value}]")
                return False

            self.current_value = value
            if session:
                session.add(self)
                session.commit()
            
            logger.debug(f"[Sensor {self.id}] Update successful. Device: {self.device.name if self.device else 'None'}, "
                         f"Room: {self.device.room.name if self.device and self.device.room else 'None'}")
            return True
        except Exception as e:
            logger.error(f"[Sensor {self.id}] Update error: {str(e)}")
            if session:
                session.rollback()
            return False

    def set_error(self, error_definition: str) -> bool:
        """Set an error condition for the sensor"""
        try:
            self.error_definition = error_definition
            session = db_session()
            session.add(self)
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting sensor error: {str(e)}")
            return False

    def clear_error(self) -> bool:
        """Clear any error condition"""
        try:
            self.error_definition = None
            session = db_session()
            session.add(self)
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error clearing sensor error: {str(e)}")
            return False

    @classmethod
    def get_by_device(cls, device_id: int):
        """Get all sensors for a device"""
        try:
            session = db_session()
            return session.query(cls).filter_by(device_id=device_id).all()
        except Exception as e:
            logger.error(f"Error getting sensors for device {device_id}: {str(e)}")
            return []

    @classmethod
    def get_all(cls) -> List["Sensor"]:
        """Get all sensors"""
        try:
            with SessionLocal() as session:
                return session.query(cls).options(
                    joinedload(cls.device).joinedload(Device.container)
                ).all()
        except Exception as e:
            logger.error(f"Error getting all sensors: {str(e)}")
            return []

    def __repr__(self):
        return f"<Sensor(name='{self.name}', type='{self.type}', value={self.current_value}{self.unit})>"

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

    def simulate(self):
        """Update sensor value based on type"""
        if self.type == 'temperature':
            self.current_value = self.base_value + random.uniform(-2, 2)
        elif self.type == 'motion':
            self.current_value = random.choice([True, False])
        # Add other sensor types...

    def _calculate_simulated_value(self):
        """This method is no longer needed, moved to Simulator."""
        pass

    def _apply_error(self, value):
        """This method is no longer needed, moved to Simulator."""
        pass

# Add SQLAlchemy event listener to ensure _simulator exists on loaded instances
@event.listens_for(Sensor, 'load')
def receive_load(target, context):
    if not hasattr(target, '_simulator'):
        target._simulator = None