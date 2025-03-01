import threading
from loguru import logger
from src.database import SessionLocal
from src.models.scenario import Scenario
from src.models.container import Container
from sqlalchemy.orm import joinedload
from typing import Dict, Any, Optional, List

class StateManager:
    """
    StateManager is a singleton class responsible for maintaining state across pages.
    It provides a central repository for sharing state data between different components
    of the application ensuring consistency when navigating between pages.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the state with default values"""
        self._state = {
            "active_scenario": None,
            "selected_scenario": None,
            "active_containers": [],
            "city": None,
            "location": None,
            "last_refresh": 0
        }
        logger.info("StateManager initialized")
    
    def get_active_scenario(self) -> Optional[Scenario]:
        """Get the currently active scenario"""
        self._refresh_state_if_needed()
        return self._state["active_scenario"]
    
    def get_selected_scenario(self) -> Optional[Scenario]:
        """Get the currently selected (but not necessarily active) scenario"""
        return self._state["selected_scenario"]
    
    def set_selected_scenario(self, scenario: Optional[Scenario]):
        """Set the currently selected scenario"""
        self._state["selected_scenario"] = scenario
        logger.info(f"Selected scenario set to: {scenario.name if scenario else 'None'}")
    
    def get_active_containers(self) -> List[Container]:
        """Get all currently active containers"""
        self._refresh_state_if_needed()
        return self._state["active_containers"] 
    
    def get_containers_for_active_scenario(self) -> List[Container]:
        """Get containers associated with the active scenario"""
        active_scenario = self.get_active_scenario()
        if not active_scenario:
            return []
            
        return [c for c in self.get_active_containers() if c.scenario_id == active_scenario.id]
    
    def get_city(self) -> Optional[str]:
        """Get the currently set city for weather data"""
        return self._state["city"]
    
    def set_city(self, city: Optional[str]):
        """Set the current city for weather data"""
        self._state["city"] = city
        logger.info(f"City set to: {city}")
    
    def get_location(self) -> Optional[Dict[str, Any]]:
        """Get the currently set location data"""
        return self._state["location"]
    
    def set_location(self, location: Optional[Dict[str, Any]]):
        """Set the current location data"""
        self._state["location"] = location
        logger.info(f"Location set to: {location}")
    
    def _refresh_state_if_needed(self, force=False):
        """
        Refresh the state from the database if needed
        This ensures we're always working with the latest data
        """
        import time
        current_time = time.time()
        # Refresh every 2 seconds at most to avoid excessive database queries
        if force or (current_time - self._state["last_refresh"]) > 2:
            self._refresh_state_from_db()
            self._state["last_refresh"] = current_time
    
    def _refresh_state_from_db(self):
        """Refresh state data from the database"""
        try:
            with SessionLocal() as session:
                # Get active scenario with eager loading of containers
                active_scenario = session.query(Scenario).filter(
                    Scenario.is_active == True
                ).options(
                    joinedload(Scenario.containers)
                ).first()
                
                # Get all active containers
                active_containers = session.query(Container).filter(
                    Container.is_active == True
                ).all()
                
                # Update state
                self._state["active_scenario"] = active_scenario
                self._state["active_containers"] = active_containers
                
                # If selected_scenario is not set and there's an active scenario, set it
                if self._state["selected_scenario"] is None and active_scenario is not None:
                    self._state["selected_scenario"] = active_scenario
                
                logger.debug(f"Refreshed application state: active_scenario={active_scenario.name if active_scenario else 'None'}, active_containers={len(active_containers)}")
                
        except Exception as e:
            logger.error(f"Error refreshing state from database: {e}", exc_info=True)
    
    def notify_scenario_changed(self, scenario_id: Optional[int] = None):
        """
        Notify the state manager that a scenario has changed
        This forces a state refresh
        """
        logger.info(f"Scenario change notification received: scenario_id={scenario_id}")
        self._refresh_state_if_needed(force=True)
    
    def notify_container_changed(self, container_id: Optional[int] = None):
        """
        Notify the state manager that a container has changed
        This forces a state refresh
        """
        logger.info(f"Container change notification received: container_id={container_id}")  
        self._refresh_state_if_needed(force=True)
