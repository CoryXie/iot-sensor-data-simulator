from sqlalchemy import inspect, text
from loguru import logger
from src.database import engine, Base, db_session
from src.models.container import Container

def check_and_update_schema():
    """Check and update database schema if needed"""
    try:
        logger.info("Checking database schema...")
        inspector = inspect(engine)
        
        # Check containers table
        if 'containers' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('containers')]
            
            # Add status column if it doesn't exist
            if 'status' not in columns:
                logger.info("Adding status column to containers table")
                with engine.connect() as conn:
                    conn.execute(
                        text("ALTER TABLE containers ADD COLUMN status VARCHAR(50) DEFAULT 'stopped'")
                    )
                    conn.commit()
                logger.info("Status column added successfully")
        
        # Create tables that don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema check completed")
        
    except Exception as e:
        logger.error(f"Error updating database schema: {str(e)}")
        raise 