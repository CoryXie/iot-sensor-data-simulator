from src.database.base import Base
from loguru import logger

class BaseModel(Base):
    """Base model with common functionality"""
    __abstract__ = True

    def __init__(self):
        """Initialize the base model"""
        pass  # No arguments needed in the base class

    def save(self, session):
        """Save the model instance to the database"""
        session.add(self)
        session.commit()

    def delete(self, session):
        """Delete the model instance from the database"""
        session.delete(self)
        session.commit()

    def refresh(self, session):
        """Refresh the model instance from the database"""
        session.refresh(self)

    @classmethod
    def get_by_id(cls, id):
        try:
            session = db_session()
            return session.query(cls).get(id)
        except Exception as e:
            logger.error(f"Error getting {cls.__name__} by id {id}: {str(e)}")
            return None 