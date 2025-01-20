from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from loguru import logger
import os

# Create database directory if it doesn't exist
os.makedirs('data', exist_ok=True)

# Create database engine
engine = create_engine('sqlite:///data/telemetry_simulator.db', echo=False)

# Create session factory
Session = sessionmaker(bind=engine)
db_session = scoped_session(sessionmaker(bind=engine))

# Create declarative base
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    """Initialize the database"""
    logger.info("Initializing database")
    try:
        # Import all models
        from models.base import Base
        from models.container import Container
        from models.device import Device
        from models.sensor import Sensor
        from models.option import Option
        
        # Import and run migrations
        from utils.db_migration import check_and_update_schema
        check_and_update_schema()
        
        # Initialize Option model first
        Option.init()
        logger.debug("Options initialized")
        
        # Bind the session to models
        Container.session = db_session
        Device.session = db_session
        Sensor.session = db_session
        Option.session = db_session
        
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.exception(f"Error initializing database: {str(e)}")
        raise

def get_session():
    """Get a new database session"""
    return Session()

# Clean up session at shutdown
def shutdown_session(exception=None):
    """Remove the session at shutdown"""
    db_session.remove()
    logger.debug("Database session removed") 