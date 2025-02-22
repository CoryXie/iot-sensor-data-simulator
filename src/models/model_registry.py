"""Module to register all SQLAlchemy models."""
from loguru import logger
from src.database import Base, engine
from src.models.options import Options  # (if needed)
from src.models.device import Device
from src.models.sensor import Sensor
from src.models.container import Container
from src.models.base_model import BaseModel  # single source for the base model
from src.models.option import Option
from src.models.schedule import Schedule
from src.models.scenario import Scenario
from src.models.room import Room

def register_models():
    """Register all models using SQLAlchemy's automatic table creation"""
    # Add all model imports here
    from src.models import (
        Option, Container, Device, Sensor, 
        Scenario, Room, Schedule  # Add missing models
    )
    
    logger.info(f"Database URL in register_models: {engine.url}") # Log DB URL

    # Log tables in metadata BEFORE create_all
    logger.info("Tables in Base.metadata BEFORE create_all: %s", Base.metadata.tables.keys())

    # Create all tables in dependency order
    Base.metadata.create_all(bind=engine)

    # Log tables in metadata AFTER create_all
    logger.info("Tables in Base.metadata AFTER create_all: %s", Base.metadata.tables.keys())
    
    # Log the existing table names for diagnosis
    from sqlalchemy import inspect
    insp = inspect(engine)
    logger.info("Existing tables after create_all (from inspector): %s", insp.get_table_names())
    
    logger.success("All database tables created successfully")

# Likely implements a registry pattern for ML models
# Key features:
# - Central catalog of available AI/ML models
# - Version control for model artifacts
# - Model loading/unloading mechanisms
# - Standardized inference interfaces
