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
    """Event system for handling smart home events"""
    
    _instance = None
    _initialized = False
    
    @classmethod
    def get_instance(cls):
        """Get or create singleton instance"""
        if not cls._instance:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize event system"""
        # Initialize handlers regardless of initialization state
        # to avoid race conditions
        self.handlers = defaultdict(list)
        self.logger = logger
        self._lock = Lock()
        
        # Skip other initialization if already initialized
        if EventSystem._initialized:
            return
        
        # Set initialization flag and create other attributes
        EventSystem._initialized = True
        self._events = []
            
    async def emit(self, event_type: str, data: dict):
        """Emit an event to all registered handlers"""
        if not hasattr(self, 'handlers'):
            self.handlers = defaultdict(list)
            self.logger.warning("Handlers attribute was missing - reinitializing")
            
        if event_type in self.handlers:
            # Make a copy of the data to avoid modifying the original
            safe_data = data.copy() if isinstance(data, dict) else {"value": data}
            
            # Ensure client_id is always a string if present
            if 'client_id' in safe_data:
                if isinstance(safe_data['client_id'], dict):
                    # Convert dict to string representation
                    try:
                        safe_data['client_id'] = str(hash(frozenset(safe_data['client_id'].items())))
                        self.logger.debug(f"Converted dict client_id to string hash: {safe_data['client_id']}")
                    except Exception as e:
                        # If hashing fails, use a simpler approach
                        safe_data['client_id'] = str(safe_data['client_id'])
                        self.logger.debug(f"Converted dict client_id to simple string: {safe_data['client_id']}")
                elif safe_data['client_id'] is not None:
                    # Convert any other type to string
                    safe_data['client_id'] = str(safe_data['client_id'])
                
            for handler in self.handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        # If handler is async, await it directly
                        await handler(safe_data)
                    else:
                        # If handler is sync, run it in the default executor
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, handler, safe_data)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event_type}: {str(e)}")
                    self.logger.exception("Full traceback:")
                    handler_name = getattr(handler, '__name__', str(handler))
                    self.logger.debug(f"Handler: {handler_name}, Data: {safe_data}")
    
    def on(self, event_type: str, handler):
        """Register an event handler"""
        if not handler:
            self.logger.warning(f"Attempted to register None handler for {event_type}")
            return
            
        # Ensure handlers attribute exists
        if not hasattr(self, 'handlers'):
            self.handlers = defaultdict(list)
            self.logger.warning("Handlers attribute was missing when registering - reinitializing")

        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        # Check if handler is already registered
        if handler not in self.handlers[event_type]:
            self.handlers[event_type].append(handler)
            handler_name = getattr(handler, '__name__', str(handler))
            self.logger.debug(f"Registered handler {handler_name} for event {event_type}")
        else:
            handler_name = getattr(handler, '__name__', str(handler))
            self.logger.debug(f"Handler {handler_name} already registered for event {event_type}")
            
    def off(self, event_type: str, handler):
        """Remove an event handler"""
        # Ensure handlers attribute exists
        if not hasattr(self, 'handlers'):
            self.handlers = defaultdict(list)
            self.logger.warning("Handlers attribute was missing when removing handler - reinitializing")
            return
            
        if event_type in self.handlers and handler in self.handlers[event_type]:
            self.handlers[event_type].remove(handler)
            
    def remove_all_handlers(self, event_type: str):
        """Remove all handlers for a specific event type"""
        # Ensure handlers attribute exists
        if not hasattr(self, 'handlers'):
            self.handlers = defaultdict(list)
            self.logger.warning("Handlers attribute was missing when removing all handlers - reinitializing")
            return
            
        if event_type in self.handlers:
            self.handlers[event_type] = []
            self.logger.debug(f"Removed all handlers for event type: {event_type}")
            
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