from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

# Create base class for declarative models
Base = declarative_base()

class BaseModel(Base):
    """Base model class with common functionality"""
    __abstract__ = True
    
    def save(self):
        """Save the model instance"""
        from src.database import db_session  # Import locally
        try:
            db_session.add(self)
            db_session.commit()
            logger.debug(f"Saved {self.__class__.__name__}")
            return self
        except SQLAlchemyError as e:
            db_session.rollback()
            logger.error(f"Error saving {self.__class__.__name__}: {str(e)}")
            raise
    
    def delete(self):
        """Delete the model instance and expire it from the session"""
        from src.database import db_session  # Import locally
        try:
            # Refresh the instance to ensure we have the latest state
            self.refresh()
            
            # Delete the instance
            db_session.delete(self)
            db_session.commit()
            
            # Expire the instance from the session
            db_session.expire(self)
            logger.debug(f"Deleted {self.__class__.__name__}")
        except SQLAlchemyError as e:
            db_session.rollback()
            logger.error(f"Error deleting {self.__class__.__name__}: {str(e)}")
            raise
    
    @classmethod
    def get_all(cls):
        """Get all instances of the model"""
        from src.database import db_session  # Import locally
        try:
            result = db_session.query(cls).all()
            logger.debug(f"Retrieved {len(result)} {cls.__name__} records")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {cls.__name__}: {str(e)}")
            return []
    
    @classmethod
    def get_by_id(cls, id):
        """Get a model instance by ID"""
        from src.database import db_session  # Import locally
        try:
            if id is None:
                return None
            result = db_session.query(cls).filter(cls.id == id).first()
            logger.debug(f"Retrieved {cls.__name__} with id {id}: {'found' if result else 'not found'}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Error getting {cls.__name__} by id: {str(e)}")
            return None
    
    def refresh(self):
        """Refresh the model instance from the database"""
        from src.database import db_session  # Import locally
        try:
            db_session.refresh(self)
            logger.debug(f"Refreshed {self.__class__.__name__}")
        except SQLAlchemyError as e:
            logger.error(f"Error refreshing {self.__class__.__name__}: {str(e)}")
            # Don't raise the error, just log it
            pass