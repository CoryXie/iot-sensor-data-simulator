from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from model.models import Base
from model.container import Container
from model.device import Device
from model.sensor import Sensor
from model.option import Option
import logging

logger = logging.getLogger(__name__)

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

def init_db():
    """Initialize the database and create tables"""
    try:
        logger.info("Initializing database")
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        # Stop all active scenarios on startup
        with Session() as session:
            active_containers = session.query(Container).filter_by(is_active=True).all()
            for container in active_containers:
                logger.info(f"Stopping active scenario on startup: {container.name}")
                container.is_active = False
                container.status = 'stopped'
            session.commit()
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise 