from datetime import datetime, time
import random
from typing import Dict, List, Callable

class EventTrigger:
    """Represents a trigger condition for an event"""
    def __init__(self, sensor_type: int, condition: Callable, target_sensor_type: int = None):
        self.sensor_type = sensor_type
        self.condition = condition
        self.target_sensor_type = target_sensor_type

class SmartHomeEvent:
    """Represents a smart home event with triggers and actions"""
    def __init__(self, name: str, description: str, triggers: List[EventTrigger], actions: List[Callable]):
        self.name = name
        self.description = description
        self.triggers = triggers
        self.actions = actions
        self.is_active = True

class EmergencyEvent:
    """Represents an emergency event in the smart home"""
    def __init__(self, name: str, severity: str, affected_sensors: List[int], duration: int = 300):
        self.name = name
        self.severity = severity  # 'low', 'medium', 'high', 'critical'
        self.affected_sensors = affected_sensors
        self.duration = duration  # seconds
        self.start_time = None
        self.is_active = False

    def start(self):
        """Start the emergency event"""
        self.start_time = datetime.now()
        self.is_active = True

    def is_expired(self):
        """Check if the emergency event has expired"""
        if not self.is_active or not self.start_time:
            return True
        return (datetime.now() - self.start_time).total_seconds() > self.duration

class EventSystem:
    """Main event system for managing smart home events"""
    def __init__(self):
        self.events: Dict[str, SmartHomeEvent] = {}
        self.emergency_events: Dict[str, EmergencyEvent] = {}
        self.scheduled_events: List[tuple] = []  # [(time, event_name), ...]
        self.alerts = []

    def add_event(self, event: SmartHomeEvent):
        """Add a new event to the system"""
        self.events[event.name] = event

    def add_emergency_event(self, event: EmergencyEvent):
        """Add a new emergency event to the system"""
        self.emergency_events[event.name] = event

    def schedule_event(self, event_time: time, event_name: str):
        """Schedule an event to occur at a specific time"""
        self.scheduled_events.append((event_time, event_name))
        self.scheduled_events.sort(key=lambda x: x[0])

    def process_sensor_update(self, sensor_type: int, value: float, room: str):
        """Process a sensor update and trigger relevant events"""
        triggered_events = []
        
        # Check regular events
        for event in self.events.values():
            if not event.is_active:
                continue
                
            for trigger in event.triggers:
                if trigger.sensor_type == sensor_type and trigger.condition(value):
                    triggered_events.append(event)
                    for action in event.actions:
                        action()

        # Check emergency conditions
        self._check_emergency_conditions(sensor_type, value, room)
        
        return triggered_events

    def _check_emergency_conditions(self, sensor_type: int, value: float, room: str):
        """Check for emergency conditions based on sensor values"""
        # Smoke detection
        if sensor_type == 25 and value > 50:  # Smoke detector
            self._trigger_emergency("Fire", "critical", [25, 0, 8], room)
        
        # Carbon monoxide detection
        elif sensor_type == 26 and value > 30:  # CO detector
            self._trigger_emergency("CO Alert", "critical", [26], room)
        
        # Water leak detection
        elif sensor_type == 27 and value == 1:  # Water leak
            self._trigger_emergency("Water Leak", "high", [27, 2], room)
        
        # Temperature extremes
        elif sensor_type == 0 and (value > 35 or value < 5):  # Temperature
            self._trigger_emergency("Temperature Extreme", "medium", [0, 8], room)

    def _trigger_emergency(self, name: str, severity: str, sensors: List[int], room: str):
        """Trigger an emergency event"""
        if name not in self.emergency_events:
            event = EmergencyEvent(name, severity, sensors)
            self.add_emergency_event(event)
        
        event = self.emergency_events[name]
        if not event.is_active:
            event.start()
            self.alerts.append({
                "type": "emergency",
                "name": name,
                "severity": severity,
                "room": room,
                "time": datetime.now()
            })

    def process_scheduled_events(self, current_time: time = None):
        """Process scheduled events"""
        if current_time is None:
            current_time = datetime.now().time()

        triggered = []
        for event_time, event_name in self.scheduled_events:
            if event_time <= current_time and event_name in self.events:
                event = self.events[event_name]
                if event.is_active:
                    for action in event.actions:
                        action()
                    triggered.append(event_name)

        return triggered

    def get_active_emergencies(self):
        """Get list of active emergency events"""
        active = []
        for event in self.emergency_events.values():
            if event.is_active and not event.is_expired():
                active.append(event)
            elif event.is_active and event.is_expired():
                event.is_active = False
        return active

    def get_alerts(self, clear=True):
        """Get and optionally clear alerts"""
        alerts = self.alerts.copy()
        if clear:
            self.alerts = []
        return alerts 