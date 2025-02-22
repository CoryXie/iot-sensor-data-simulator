from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship, backref, Mapped
from src.models.base_model import BaseModel
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from src.models.container import Container

class Scenario(BaseModel):
    """Scenario model for smart home scenarios"""
    __tablename__ = 'scenarios'
    __table_args__ = {'extend_existing': True}  # Add for SQLite compatibility
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    is_active = Column(Boolean, default=False)
    scenario_type = Column(String(50)) # e.g., 'routine', 'standard', 'night'
    description = Column(Text)
    
    # Corrected relationship
    containers = relationship(
        "Container",
        back_populates="scenario",
        cascade="all, delete-orphan",
        foreign_keys="Container.scenario_id"
    )

    def __init__(self, name: str, scenario_type: str, is_active: bool = False, description: Optional[str] = None):
        """Initialize a scenario"""
        super().__init__()
        self.name = name
        self.is_active = is_active
        self.scenario_type = scenario_type
        self.description = description

    def toggle(self):
        """Toggle scenario state with mutual exclusivity"""
        from src.database import db_session
        with db_session() as session:
            # Deactivate all other scenarios
            session.query(Scenario).update({'is_active': False})
            # Toggle current scenario
            self.is_active = not self.is_active
            session.add(self)
            session.commit()
        
        if self.is_active:
            self.start_simulation()
        else:
            self.stop_simulation()

    def activate(self):
        """Activate scenario by starting related containers"""
        from src.utils.smart_home_simulator import SmartHomeSimulator
        simulator = SmartHomeSimulator.instance()
        
        for container in self.containers:
            container.start()  # Use start() instead of activate()
            simulator.start_container(container)

    def deactivate(self):
        """Deactivate scenario by stopping containers"""
        for container in self.containers:
            container.stop()  # Use stop() instead of deactivate()

# Defines simulation/experiment scenarios with:
# - Scenario configuration parameters
# - Environment variables
# - Temporal constraints
# - Relationships to devices/sensors 