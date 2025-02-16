from typing import Optional, List, ClassVar
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped, joinedload
from datetime import datetime
from src.models.base_model import BaseModel
from src.utils.mqtt_helper import MQTTHelper
from src.utils.container_thread import ContainerThread
from src.constants.units import *
from src.database import db_session, SessionLocal
from nicegui import ui
from loguru import logger
from src.models.option import Option
from src.models.device import Device
import json
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.sensor import Sensor
    from src.models.scenario import Scenario

class Container(BaseModel):
    """Container model for grouping devices"""
    __tablename__ = 'containers'
    __table_args__ = {'extend_existing': True}  # Add this for SQLite compatibility

    id: Mapped[int] = Column(Integer, primary_key=True)
    name: Mapped[str] = Column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = Column(String(200))
    container_type: Mapped[str] = Column(String(50))
    location: Mapped[Optional[str]] = Column(String(50))
    is_active: Mapped[bool] = Column(Boolean, default=False)
    start_time: Mapped[Optional[datetime]] = Column(DateTime, default=None)
    status: Mapped[str] = Column(String(20), default='stopped')  # running, stopped, error
    created_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    interval: Mapped[int] = Column(Integer, default=5)

    # Relationships
    devices: Mapped[List["Device"]] = relationship(
        "Device", 
        back_populates="container", 
        cascade="all, delete-orphan",
        lazy="joined",  # Force eager loading
        order_by="Device.name"
    )

    scenario = relationship(
        "Scenario", 
        back_populates="container",  # Match the back_populates name
        uselist=False,
        cascade="all, delete-orphan"
    )

    sensors: Mapped[List["Sensor"]] = relationship(
        "Sensor",
        back_populates="container",
        foreign_keys="Sensor.container_id",
        cascade="all, delete-orphan"
    )

    # Runtime attributes (not mapped to database)
    _thread: ClassVar[Optional[ContainerThread]] = None
    _mqtt_helper: ClassVar[Optional[MQTTHelper]] = None

    def __init__(self, name: str, container_type: str = 'scenario', description: str = None, is_active: bool = False, location: str = None, interval: int = 5):
        """Initialize a container
        
        Args:
            name: Container name
            container_type: Type of container
            description: Optional container description
            is_active: Whether the container is active
            location: Optional location
            interval: Interval for container logic
        """
        super().__init__()
        self.name = name
        self.container_type = container_type
        self.description = description
        self.is_active = is_active
        self.location = location
        self.interval = interval
        self.scenario = None  # Initialize scenario relationship
        self._thread = None
        self._mqtt_helper = None

    def run_logic(self):
        """Run the container logic and sensor updates"""
        if self.is_active:
            try:
                self._mqtt_helper = MQTTHelper(f"container_{self.id}")
                
                for device in self.devices:
                    for sensor in device.sensors:
                        sensor.simulate_value(db_session())
                        
                self.publish_sensor_data()
                self.status = 'running'
            except Exception as e:
                logger.error(f"Container logic error: {str(e)}")
                self.status = 'error'

    def start(self):
        """Start the container and all its devices"""
        try:
            with SessionLocal() as session:
                db_container = session.query(Container).get(self.id)
                if not db_container.is_active:
                    db_container.is_active = True
                    db_container.status = 'running'
                    db_container.start_time = datetime.now()
                    
                    # Create and start thread
                    self._thread = ContainerThread(target=self._run_container_logic)
                    self._thread.start()
                    
                    session.commit()
                    logger.info(f"Started container {self.name}")
                    return True
        except Exception as e:
            logger.error(f"Error starting container {self.name}: {str(e)}")
            return False

    def _simulate_sensors(self, session):
        """Simulates sensor data for all devices in the container."""
        if not self.is_active:
            return

        for device in self.devices:
            for sensor in device.sensors:
                sensor.simulate_value(session) # Pass session to simulate_value

    def stop(self):
        """Stop the container and all its devices"""
        try:
            with SessionLocal() as session:
                db_container = session.query(Container).get(self.id)
                if db_container.is_active:
                    db_container.is_active = False
                    db_container.status = 'stopped'
                    db_container.start_time = None
                    session.commit()

                    if self._thread and self._thread.is_alive():
                        self._thread.stop()
                        self._thread.join(timeout=5)
                    
                    logger.info(f"Stopped container {self.name}")
                    return True
        except Exception as e:
            logger.error(f"Error stopping container {self.name}: {str(e)}")
            return False

    @classmethod
    def get_by_name(cls, name: str) -> Optional['Container']:
        """Get a container by its name"""
        try:
            with SessionLocal() as session:
                return session.query(cls).filter_by(name=name).first()
        except Exception as e:
            logger.error(f"Error getting container by name {name}: {str(e)}")
            return None

    @classmethod
    def stop_all(cls):
        """Stop all active containers"""
        try:
            session = db_session()
            active_containers = session.query(cls).filter_by(is_active=True).all()
            for container in active_containers:
                container.stop()
            logger.info("All containers stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping all containers: {str(e)}")
            return False

    @classmethod
    def get_all(cls) -> List["Container"]:
        """Get all containers"""
        try:
            with SessionLocal() as session:
                return session.query(cls).options(
                    joinedload(cls.devices).joinedload(Device.sensors)
                ).all()
        except Exception as e:
            logger.error(f"Error getting all containers: {str(e)}")
            return []

    @classmethod
    def add(cls, name: str, description: str = None, container_type: str = None, is_active: bool = False, location: str = None) -> 'Container':
        """Add a new container"""
        try:
            session = db_session()
            container = cls(name=name, description=description, container_type=container_type, is_active=is_active, location=location)
            session.add(container)
            session.commit()
            return container
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding container: {str(e)}")
            raise

    def __repr__(self):
        return f"<Container(name='{self.name}', location='{self.location}', status='{self.status}')>"

    def publish_sensor_data(self):
        """Publish sensor data to MQTT broker"""
        if self._mqtt_helper and self.is_active:
            try:
                data = {
                    'container_id': self.id,
                    'name': self.name,
                    'timestamp': datetime.now().isoformat(),
                    'devices': []
                }
                
                for device in self.devices:
                    device_data = {
                        'device_id': device.id,
                        'name': device.name,
                        'type': device.type,
                        'sensors': []
                    }
                    
                    for sensor in device.sensors:
                        sensor_data = {
                            'sensor_id': sensor.id,
                            'name': sensor.name,
                            'type': sensor.type,
                            'value': sensor.current_value,
                            'unit': sensor.unit
                        }
                        device_data['sensors'].append(sensor_data)
                    
                    data['devices'].append(device_data)
                
                self._mqtt_helper.publish(json.dumps(data))
            except Exception as e:
                logger.error(f"Error publishing sensor data: {e}")

    def _publish_sensor_data(self, sensor, value):
        """Publish sensor data to MQTT broker"""
        mqtt = MQTTHelper.get_instance()
        topic = f"containers/{self.id}/sensors/{sensor.id}"
        payload = f"{sensor.name},{value}"
        mqtt.publish(topic, payload)

    def refresh(self, session=None):
        """Refresh the container from the database"""
        try:
            if session is None:
                with db_session() as new_session:
                    new_session.add(self)
                    new_session.refresh(self)
            else:
                session.add(self)
                session.refresh(self)
        except Exception as e:
            logger.error(f"Error refreshing container: {e}")
            raise

    def _run_container_logic(self):
        """Main container logic loop"""
        logger.info(f"Starting container logic for {self.name}")
        while self.is_active:
            try:
                with SessionLocal() as session:
                    # Get fresh container instance for this iteration
                    db_container = session.query(Container).options(
                        joinedload(Container.devices)
                        .joinedload(Device.sensors)
                    ).get(self.id)

                    if not db_container:
                        logger.error(f"Container {self.id} not found in database")
                        break

                    # Simulate sensor values
                    db_container._simulate_sensors(session)
                    
                    # Publish data
                    db_container.publish_sensor_data()

                    # Calculate sleep time
                    start_time = datetime.now()
                    elapsed = (datetime.now() - start_time).total_seconds()
                    sleep_time = max(0, self.interval - elapsed)
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Container thread error: {str(e)}")
                self.status = 'error'
                break
            
        logger.info(f"Stopping container logic for {self.name}")
        with SessionLocal() as cleanup_session:
            cleanup_container = cleanup_session.query(Container).get(self.id)
            if cleanup_container:
                cleanup_container.is_active = False
                cleanup_container.status = 'stopped'
                cleanup_session.commit()

    def add_device(self, device: 'Device'):
        """Add a device to the container"""
        if device not in self.devices:
            self.devices.append(device)

    def remove_device(self, device: 'Device'):
        """Remove a device from the container"""
        if device in self.devices:
            self.devices.remove(device)

    def add_sensor(self, sensor: 'Sensor'):
        """Add a sensor to the container"""
        if sensor not in self.sensors:
            self.sensors.append(sensor)

    def remove_sensor(self, sensor: 'Sensor'):
        """Remove a sensor from the container"""
        if sensor in self.sensors:
            self.sensors.remove(sensor)