from sqlalchemy import Column, Integer, String, Float, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from loguru import logger

Base = declarative_base()


class OptionModel(Base):
    '''This class represents an option. Options are used to store global settings.'''
    __tablename__ = 'option'
    session = None

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    value = Column(String(255))

    def __repr__(self):
        return f"<Option(id={self.id}, name={self.name}, value={self.value})>"


class ContainerModel(Base):
    '''This class represents a container. A container is a collection of devices. Used for defining the database schema.'''
    __tablename__ = 'container'
    session = None

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    description = Column(String(255))
    location = Column(String(255))
    is_active = Column(Boolean)
    start_time = Column(TIMESTAMP)

    devices = relationship("Device", back_populates="container")

    def __repr__(self):
        return f"<Container(id={self.id}, name={self.name}, description={self.description}, location={self.location}, is_active={self.is_active}, start_time={self.start_time})>"


class DeviceModel(Base):
    '''This class represents a device. A device is a collection of sensors. Used for defining the database schema.'''
    __tablename__ = 'device'
    session = None
    client = None

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    generation_id = Column(Integer)
    etag = Column(String(255))
    status = Column(String(255))
    connection_string = Column(String(255))
    container_id = Column(Integer, ForeignKey(ContainerModel.id))

    container = relationship("ContainerModel", back_populates="devices")
    sensors = relationship("Sensor", back_populates="device")

    def __repr__(self):
        return f"<Device(id={self.id}, name={self.name}, generation_id={self.generation_id}, etag={self.etag}, status={self.status}, connection_string={self.connection_string}, container_id={self.container_id})>"


class SensorModel(Base):
    '''This class represents a sensor. Used for defining the database schema.'''
    __tablename__ = 'sensor'
    session = None
    thread = None

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    base_value = Column(Float)
    unit = Column(Integer)
    variation_range = Column(Float)
    change_rate = Column(Float)
    interval = Column(Float)
    error_definition = Column(String(500))
    device_id = Column(Integer, ForeignKey(DeviceModel.id))

    device = relationship(DeviceModel, back_populates='sensors')

    def __repr__(self):
        return f"<Sensor(id={self.id}, name={self.name}, base_value={self.base_value}, unit={self.unit}, variation_range={self.variation_range}, change_rate={self.change_rate}, interval={self.interval}, device_id={self.device_id})>"
