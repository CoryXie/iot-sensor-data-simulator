from typing import List, Callable, Any
from datetime import datetime, timedelta
from loguru import logger
from collections import defaultdict
from threading import Lock
import asyncio

class EventTrigger:
    """Class representing a trigger condition for an event"""
    
    def __init__(self, sensor_type: int, condition: Callable[[float], bool], target_type: int = None):
        self.sensor_type = sensor_type
        self.condition = condition
        self.target_type = target_type
        self.last_triggered = None
        logger.debug(f"Created event trigger for sensor type {sensor_type}")
        
    def check(self, value: float) -> bool:
        """Check if the trigger condition is met"""
        if self.condition(value):
            # Prevent rapid re-triggering by requiring a minimum time between triggers
            if not self.last_triggered or (datetime.now() - self.last_triggered) > timedelta(seconds=5):
                self.last_triggered = datetime.now()
                logger.debug(f"Trigger condition met for sensor type {self.sensor_type} with value {value}")
                return True
        return False

class SmartHomeEvent:
    """Class representing a smart home event with triggers and actions"""
    
    def __init__(self, name: str, description: str, triggers: List[EventTrigger], actions: List[Callable[[], None]]):
        self.name = name
        self.description = description
        self.triggers = triggers
        self.actions = actions
        self.is_active = False
        self.start_time = None
        self.severity = 'normal'
        logger.info(f"Created smart home event: {name}")
        
    def trigger(self):
        """Trigger the event's actions"""
        self.is_active = True
        self.start_time = datetime.now()
        logger.info(f"Triggered event: {self.name}")
        for action in self.actions:
            try:
                action()
            except Exception as e:
                logger.error(f"Error executing action for event {self.name}: {str(e)}")
            
    def check_expiration(self):
        """Check if the event has expired"""
        if self.is_active and self.start_time:
            # Events expire after 5 minutes
            if (datetime.now() - self.start_time) > timedelta(minutes=5):
                self.is_active = False
                self.start_time = None
                logger.debug(f"Event expired: {self.name}")
                return True
        return False

class EventSystem:
    """Event system for handling sensor updates and other events"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.handlers = {}
            self.logger = logger
            self._events = []
            self._lock = Lock()
            
    async def emit(self, event_type: str, data: dict):
        """Emit an event to all registered handlers"""
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        # If handler is async, await it directly
                        await handler(data)
                    else:
                        # If handler is sync, run it in the default executor
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, handler, data)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event_type}: {str(e)}")
                    self.logger.debug(f"Handler: {handler.__name__}, Data: {data}")
    
    def on(self, event_type: str, handler):
        """Register an event handler"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        if handler not in self.handlers[event_type]:
            self.handlers[event_type].append(handler)
            
    def off(self, event_type: str, handler):
        """Remove an event handler"""
        if event_type in self.handlers and handler in self.handlers[event_type]:
            self.handlers[event_type].remove(handler)
            
    def add_event(self, event: SmartHomeEvent):
        """Add an event to the system"""
        self._events.append(event)
        logger.info(f"Added event to system: {event.name}")
        
    def add_emergency(self, event: SmartHomeEvent):
        """Add an emergency event to the system"""
        event.severity = 'emergency'
        self._events.append(event)
        logger.info(f"Added emergency event to system: {event.name}")
        
    def process_sensor_update(self, sensor_type: int, value: float, room_type: str = None):
        """Process a sensor update and check for triggered events"""
        try:
            # Check regular events
            for event in self._events:
                for trigger in event.triggers:
                    if trigger.sensor_type == sensor_type:
                        if room_type and trigger.target_type and trigger.target_type != room_type:
                            continue
                        if trigger.check(value):
                            logger.info(f"Sensor update triggered event: {event.name} (sensor type: {sensor_type}, value: {value})")
                            event.trigger()
            
            # Check emergency events
            for event in self._events:
                for trigger in event.triggers:
                    if trigger.sensor_type == sensor_type:
                        if room_type and trigger.target_type and trigger.target_type != room_type:
                            continue
                        if trigger.check(value):
                            logger.warning(f"Sensor update triggered emergency event: {event.name} (sensor type: {sensor_type}, value: {value})")
                            event.trigger()
            
            # Clean up expired events
            self._cleanup_expired_events()
        except Exception as e:
            logger.exception(f"Error processing sensor update: {str(e)}")
    
    def _cleanup_expired_events(self):
        """Clean up expired events"""
        try:
            for event in self._events:
                if event.check_expiration():
                    logger.debug(f"Cleaned up expired event: {event.name}")
        except Exception as e:
            logger.exception(f"Error cleaning up expired events: {str(e)}")
    
    def get_active_emergencies(self) -> List[SmartHomeEvent]:
        """Get list of active emergency events"""
        return [event for event in self._events if event.is_active]