from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import BaseModel, db_session

class Container(BaseModel):
    """Container model for grouping devices"""
    __tablename__ = 'containers'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)
    description = Column(String(200))
    location = Column(String(50))
    is_active = Column(Boolean, default=False)
    message_count = Column(Integer, default=0)
    start_time = Column(DateTime)
    
    # Relationships
    devices = relationship("Device", back_populates="container", cascade="all, delete-orphan")
    
    @classmethod
    def add(cls, name: str, description: str = None, location: str = None) -> 'Container':
        """Add a new container"""
        try:
            container = cls(
                name=name,
                description=description,
                location=location,
                is_active=False,
                message_count=0
            )
            container.save()
            return container
        except Exception as e:
            print(f"Error adding container: {str(e)}")
            raise

    @classmethod
    def get_by_name(cls, name: str) -> Optional['Container']:
        """Get a container by name"""
        try:
            return db_session.query(cls).filter(cls.name == name).first()
        except Exception as e:
            print(f"Error getting container by name: {str(e)}")
            return None

    def start(self, interface=None):
        """Start the container"""
        try:
            self.is_active = True
            self.start_time = datetime.utcnow()
            self.save()
        except Exception as e:
            print(f"Error starting container: {str(e)}")
            raise

    def stop(self):
        """Stop the container"""
        try:
            self.is_active = False
            self.start_time = None
            self.save()
        except Exception as e:
            print(f"Error stopping container: {str(e)}")
            raise

    def increment_message_count(self):
        """Increment the message count"""
        try:
            self.message_count += 1
            self.save()
        except Exception as e:
            print(f"Error incrementing message count: {str(e)}")
            raise

    def delete(self):
        """Delete the container and all associated devices"""
        try:
            # Stop if active
            if self.is_active:
                self.stop()
            
            # Merge the instance into the session if it's not tracked
            if not db_session.is_active:
                db_session.begin()
            if not db_session.object_session(self):
                self = db_session.merge(self)
            
            # Delete from database
            db_session.delete(self)
            db_session.commit()
            
        except Exception as e:
            db_session.rollback()
            print(f"Error deleting container: {str(e)}")
            raise 