from models.base import Base, db_session, engine

def init_db():
    """Initialize the database, creating all tables"""
    # Import all models here to ensure they are known to SQLAlchemy
    import models.container
    import models.device
    import models.sensor
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
def get_session():
    """Get the current database session"""
    return db_session 