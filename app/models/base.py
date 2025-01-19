from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import configure_mappers, scoped_session, sessionmaker
from sqlalchemy import create_engine
import os

# Use environment variable for database URL or default to SQLite
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
db_session = scoped_session(sessionmaker(autocommit=False,
                                       autoflush=False,
                                       bind=engine))

# Create base class for declarative models
Base = declarative_base()
Base.query = db_session.query_property()

# Configure mappers to not warn about unmatched deletes
configure_mappers()

class BaseModel(Base):
    """Base model class with common functionality"""
    __abstract__ = True
    
    def save(self):
        """Save the model instance"""
        try:
            db_session.add(self)
            db_session.commit()
            return self
        except SQLAlchemyError as e:
            db_session.rollback()
            print(f"Error saving {self.__class__.__name__}: {str(e)}")
            raise
    
    def delete(self):
        """Delete the model instance and expire it from the session"""
        try:
            # Refresh the instance to ensure we have the latest state
            self.refresh()
            
            # Delete the instance
            db_session.delete(self)
            db_session.commit()
            
            # Expire the instance from the session
            db_session.expire(self)
        except SQLAlchemyError as e:
            db_session.rollback()
            print(f"Error deleting {self.__class__.__name__}: {str(e)}")
            raise
    
    @classmethod
    def get_all(cls):
        """Get all instances of the model"""
        try:
            return db_session.query(cls).all()
        except SQLAlchemyError as e:
            print(f"Error getting all {cls.__name__}: {str(e)}")
            return []
    
    @classmethod
    def get_by_id(cls, id):
        """Get a model instance by ID"""
        try:
            if id is None:
                return None
            return db_session.query(cls).filter(cls.id == id).first()
        except SQLAlchemyError as e:
            print(f"Error getting {cls.__name__} by id: {str(e)}")
            return None
    
    def refresh(self):
        """Refresh the model instance from the database"""
        try:
            db_session.refresh(self)
        except SQLAlchemyError as e:
            print(f"Error refreshing {self.__class__.__name__}: {str(e)}")
            # Don't raise the error, just log it
            pass 