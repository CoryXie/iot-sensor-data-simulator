from sqlalchemy import Column, String, Integer, ForeignKey
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
    
    # Relationships
    devices = relationship("Device", back_populates="room")
    sensors = relationship("Sensor", back_populates="room")
    
    def __init__(self, name: str, room_type: str, description: str = None):
        super().__init__()
        self.name = name
        self.room_type = room_type
        self.description = description

    def __repr__(self):
        return f"<Room(name='{self.name}', type='{self.room_type}')>" 