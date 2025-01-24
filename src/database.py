from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from src.models.base import Base
from loguru import logger
import os

# Create database directory if it doesn't exist
os.makedirs('data', exist_ok=True)

# Create database engine
engine = create_engine('sqlite:///data/app.db')

# Create session factory
Session = sessionmaker(bind=engine)
db_session = scoped_session(sessionmaker(autocommit=False,
                                       autoflush=False,
                                       bind=engine))


Base.query = db_session.query_property()


def get_session():
    """Get a new database session"""
    return Session()