from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from loguru import logger
import os

# Create database directory if it doesn't exist
os.makedirs('data', exist_ok=True)

# Create database engine
engine = create_engine('sqlite:///data/telemetry_simulator.db')

# Create scoped session factory
Session = sessionmaker(bind=engine)
db_session = scoped_session(Session)

def init_db():
    """Initialize the database"""
    logger.info("Initializing database")
    try:
        # Import all models that need to be created
        from models.base import Base
        from models.container import Container
        from models.device import Device
        from models.sensor import Sensor
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        # Bind the session to models
        Container.session = db_session
        Device.session = db_session
        Sensor.session = db_session
        
        # Try to import and bind Option model if it exists
        try:
            from models.option import Option
            Option.session = db_session
            logger.debug("Option model initialized")
        except ImportError:
            logger.debug("Option model not available")
        
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