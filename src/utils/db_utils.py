
from src.database import db_session, engine, Base
from loguru import logger
import os

# Import model classes at the top, to register them with Base.metadata
from src.models.option import Option
from src.models.container import Container
from src.models.device import Device
from src.models.sensor import Sensor

def init_db():
    """Initialize the database"""
    try:
        logger.info("Initializing database")

        database_path = 'data/app.db'
        if os.path.exists(database_path):
            os.remove(database_path)
            logger.info(f"Deleted existing database file: {database_path}")
        logger.info(f"Using database file: {os.path.abspath(database_path)}")

        # Create all tables using metadata
        Base.metadata.create_all(engine)
        db_session.commit()
        logger.info("Database initialized successfully (tables created)")

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        db_session.rollback()
        raise
    finally:
        db_session.remove()

def shutdown_db():
    """Cleanup database session"""
    db_session.remove()

def get_session():
    """Get a new database session"""
    return Session()