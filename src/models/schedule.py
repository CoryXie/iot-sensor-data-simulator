from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from src.models.base_model import BaseModel
from datetime import datetime
from src.database import db_session
from loguru import logger
from typing import Optional

class Schedule(BaseModel):
    """Model representing a scheduled scenario"""
    __tablename__ = 'schedules'

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False)
    trigger_time = Column(DateTime, nullable=False)
    action = Column(String(50), nullable=False)  # 'start' or 'stop'
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, scenario_id: int, trigger_time: datetime, action: str):
        self.scenario_id = scenario_id
        self.trigger_time = trigger_time
        self.action = action

    @classmethod
    def add_schedule(cls, scenario_id: int, trigger_time: datetime, action: str) -> 'Schedule':
        """Add a new schedule"""
        try:
            session = db_session()
            schedule = cls(
                scenario_id=scenario_id,
                trigger_time=trigger_time,
                action=action
            )
            session.add(schedule)
            session.commit()
            return schedule
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding schedule: {str(e)}")
            raise

    @classmethod
    def get_all(cls):
        """Get all schedules"""
        try:
            session = db_session()
            return session.query(cls).all()
        except Exception as e:
            logger.error(f"Error getting all schedules: {str(e)}")
            return []

    @classmethod
    def delete_by_id(cls, schedule_id: int) -> bool:
        """Delete a schedule by its ID"""
        try:
            session = db_session()
            schedule = session.query(cls).filter(cls.id == schedule_id).first()
            if schedule:
                session.delete(schedule)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting schedule: {str(e)}")
            return False