import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
import stat
from loguru import logger
import sqlalchemy
import time
import fcntl  # For file locking
from sqlalchemy import text
from contextlib import contextmanager
from sqlalchemy import inspect
from .base import Base  # Use shared Base definition

load_dotenv()  # Load environment variables from .env file

# Create database directory if it doesn't exist
DB_DIR = os.path.join(os.getcwd(), 'data')
os.makedirs(DB_DIR, exist_ok=True, mode=0o755)  # 0o755 = rwxr-xr-x
logger.info(f"Database directory ensured: {DB_DIR}")

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/simulation.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite specific
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database tables and initial data"""
    logger.info("init_db: Initializing database tables...")
    
    try:
        with engine.connect() as conn:
            # Import all models to ensure proper registration
            from src.models import BaseModel  # Triggers model imports
            from src.models.option import Option
            
            logger.info("Creating all tables...")
            Base.metadata.create_all(conn)
            conn.commit()
            logger.info("init_db: Database tables created")
            
            # Verify options table exists
            if inspect(conn).has_table("options"):
                logger.info("Initializing default options...")
                Option.set_value('demo_mode', 'false')
                logger.info("Default options initialized")
            else:
                logger.error("Options table not created!")
                raise RuntimeError("Database schema incomplete")
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def get_db():
    """Get a database session"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@contextmanager
def db_session():
    """Proper context manager for database sessions"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def check_schema():
    """Check if the database schema is correct.
    
    This function uses SQLAlchemy's Inspector to retrieve the list of tables
    and their columns, then compares them with the expected schema.
    """
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    # Updated expected tables list
    expected_tables = {
        'containers', 'devices', 'sensors',
        'scenarios', 'rooms', 'options'
    }
    
    # Retrieve existing tables
    existing_tables = set(inspector.get_table_names())
    
    logger.info(f"Expected tables: {expected_tables}")
    logger.info(f"Existing tables: {existing_tables}")
    
    missing_tables = expected_tables - existing_tables
    extra_tables = existing_tables - expected_tables
    
    if missing_tables:
        logger.error(f"Schema check failed. Missing tables: {missing_tables}")
    else:
        logger.info("All expected tables are present.")
    
    if extra_tables:
        logger.warning(f"Extra tables found: {extra_tables}")

    # Optionally, check the columns of each expected table:
    for table in expected_tables:
        try:
            columns = [col['name'] for col in inspector.get_columns(table)]
            logger.info(f"Columns in table '{table}': {columns}")
        except Exception as e:
            logger.error(f"Error retrieving columns for table {table}: {e}")

def ensure_database():
    """Ensure database is initialized with all required tables"""
    try:
        logger.info("ensure_database: Starting database initialization process")
        init_db()
        check_schema()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

# Implements database abstraction layer with:
# - SQLAlchemy engine configuration
# - Session management
# - Connection pooling
# - Base model inheritance
# - Migration capabilities