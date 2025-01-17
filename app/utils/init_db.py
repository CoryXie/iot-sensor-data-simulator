from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from model.models import Base
from model.container import Container
from model.device import Device
from model.sensor import Sensor
from model.option import Option

def init_database():
    """Initialize the database and set up sessions for all models"""
    # Create database engine
    engine = create_engine('sqlite:///telemetry_simulator.db')
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Create session factory
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Set session for all models
    Container.session = session
    Device.session = session
    Sensor.session = session
    Option.session = session
    
    return engine, session 