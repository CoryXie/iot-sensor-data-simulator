from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from loguru import logger
from src.database import Base, engine, SessionLocal

def init_db():
    """Initialize the database"""
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def get_session():
    """Get a new database session"""
    return SessionLocal()

def shutdown_db():
    """Shutdown database connection"""
    try:
        # Close the engine connection pool
        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {str(e)}")