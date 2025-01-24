from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from src.models.base import BaseModel
from src.database import db_session
from src.utils.mqtt_helper import MQTTHelper
from src.utils.container_thread import ContainerThread
from src.constants.units import *
from nicegui import ui
from loguru import logger

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
    status = Column(String(50), default='stopped')
    
    # Relationships
    devices = relationship("Device", back_populates="container", cascade="all, delete-orphan")
    
    message_count = None
    device_clients = {}
    thread = None

    def __init__(self, *args, **kwargs):
        '''Initializes the container'''
        super().__init__(*args, **kwargs)
        self.thread = None
        logger.debug(f"Initialized container: {self.name if hasattr(self, 'name') else 'unnamed'}")

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

    @classmethod
    def get_by_id(cls, id):
        """Get container by ID"""
        try:
            return db_session.query(cls).filter_by(id=id).first()
        except Exception as e:
            logger.error(f"Error getting container by ID: {str(e)}")
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
            self.status = 'stopped'
            self.start_time = None
            self.save()
            logger.info(f"Container {self.name} stopped")
        except Exception as e:
            logger.error(f"Error stopping container {self.name}: {str(e)}")
            raise

    @classmethod
    def stop_all(cls):
        """Stop all active containers"""
        try:
            active_containers = db_session.query(cls).filter_by(is_active=True).all()
            for container in active_containers:
                container.is_active = False
                try:
                    container.status = 'stopped'
                except:
                    # Handle case where status column might not exist yet
                    pass
            db_session.commit()
            logger.info("All containers stopped")
        except Exception as e:
            logger.error(f"Error stopping all containers: {str(e)}")
            db_session.rollback()
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

    @classmethod
    def get_all(cls):
        """Get all containers"""
        try:
            return db_session.query(cls).all()
        except Exception as e:
            logger.error(f"Error getting all containers: {str(e)}")
            return [] 