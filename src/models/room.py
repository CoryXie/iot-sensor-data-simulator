from sqlalchemy import Column, String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from src.models.base_model import BaseModel
from src.database import Base

class Room(BaseModel):
    """Room model for smart home rooms"""
    __tablename__ = 'rooms'  # Explicit table name
    __table_args__ = {'extend_existing': True}  # For SQLite compatibility
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    room_type = Column(String(50))  # e.g., 'living_room', 'bedroom'
    description = Column(String(200))
    is_indoor = Column(Boolean, default=True)  # Most rooms are indoor by default
    
    # Correct relationships
    devices = relationship("Device", back_populates="room", cascade="all, delete-orphan")
    sensors = relationship("Sensor", back_populates="room", overlaps="room")
    
    def __init__(self, name: str, room_type: str, description: str = None, is_indoor: bool = True):
        super().__init__()
        self.name = name
        self.room_type = self._normalize_room_type(room_type)
        self.description = description
        self.is_indoor = is_indoor
        
        # Set is_indoor based on room type if not explicitly provided
        if self.room_type in ['balcony', 'patio', 'garden', 'garage', 'terrace']:
            self.is_indoor = False

    def _normalize_room_type(self, room_type: str) -> str:
        """Normalize room type for consistent comparison"""
        return room_type.lower().strip().replace(" ", "_")

    def __repr__(self):
        return f"<Room(name='{self.name}', type='{self.room_type}', {'indoor' if self.is_indoor else 'outdoor'})>" 