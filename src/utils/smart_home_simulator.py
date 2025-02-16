import random
from datetime import datetime
from typing import Dict
from loguru import logger
from src.models.device import Device
from src.models.sensor import Sensor
from src.models.container import Container
from src.utils.event_system import EventSystem
import paho.mqtt.client as mqtt
import time
import threading
from src.database import db_session
from sqlalchemy.orm import joinedload
import json
import os
import subprocess

class SmartHomeSimulator:
    """Class to handle smart home sensor value simulation"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def instance(cls):
        return cls._instance
    
    def __init__(self, event_system: EventSystem, simulation_interval=5):
        """Initializes the SmartHomeSimulator with proper env config"""
        logger.info("Initializing SmartHomeSimulator")
        self.event_system = event_system
        self.active_scenario = None
        self.sensor_threads = {}
        self.base_values = {}
        self.device_simulators = {}
        self.sensor_simulators = {}
        self.broker_address = os.getenv('MQTT_BROKER_ADDRESS', 'localhost')
        self.broker_port = int(os.getenv('MQTT_BROKER_PORT', 1883))
        self.simulation_interval = simulation_interval
        
        # Configure MQTT client with environment variables
        self.client = mqtt.Client(
            client_id=f"smart_home_sim_{random.randint(1000,9999)}",
            protocol=mqtt.MQTTv311,
            transport="tcp"
        )
        
        # Add authentication if configured
        if os.getenv('MQTT_BROKER_USERNAME'):
            self.client.username_pw_set(
                os.getenv('MQTT_BROKER_USERNAME'),
                os.getenv('MQTT_BROKER_PASSWORD')
            )
        
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        
        self.running = False
        self.simulation_thread = None
        self.connect_to_broker()
        self.start_simulation()
        self._initialize_simulators()
        
        # Add message tracking
        self._active_messages = {}  # Initialize message tracking dict
        
        # Connection management
        self.reconnect_attempts = 0  # Initialize reconnect counter
        self.max_reconnect_attempts = 10  # Set maximum reconnect attempts
        
        # Thread safety
        self._publish_lock = threading.Lock()
        
        self.db = db_session
        
    def set_scenario(self, scenario_name: str):
        """Set the current scenario for simulation"""
        logger.info(f"Setting scenario to: {scenario_name}")
        self.active_scenario = scenario_name
        self.scenario_start_time = datetime.now()
        self.base_values = {}
        
    def adjust_sensor_value(self, base_value: float, sensor_type: int) -> float:
        """Adjust a sensor value based on the current scenario and time"""
        if sensor_type not in self.base_values:
            self.base_values[sensor_type] = base_value
            logger.debug(f"Initialized base value for sensor type {sensor_type}: {base_value}")
            
        # Get time-based variation
        time_variation = self._get_time_variation(sensor_type)
        
        # Get scenario-based variation
        scenario_variation = self._get_scenario_variation(sensor_type)
        
        # Add some random noise
        noise = random.uniform(-0.5, 0.5)
        
        # Combine all variations
        adjusted_value = self.base_values[sensor_type] + time_variation + scenario_variation + noise
        logger.debug(f"Adjusted value for sensor type {sensor_type}: {adjusted_value} (base: {self.base_values[sensor_type]}, time: {time_variation}, scenario: {scenario_variation}, noise: {noise})")
        
        # Ensure the value stays within reasonable bounds
        return max(0, adjusted_value)
    
    def _get_time_variation(self, sensor_type: int) -> float:
        """Get time-based variation for a sensor type"""
        current_hour = datetime.now().hour
        
        # Temperature varies throughout the day
        if sensor_type == 0:  # Temperature
            if 0 <= current_hour < 6:  # Night
                return -2.0
            elif 6 <= current_hour < 12:  # Morning
                return 0.0
            elif 12 <= current_hour < 18:  # Afternoon
                return 2.0
            else:  # Evening
                return 0.0
        
        # Light level varies with time
        elif sensor_type == 14:  # Brightness
            if 6 <= current_hour < 18:  # Daytime
                return 50.0
            else:  # Nighttime
                return -30.0
        
        # Motion more likely during day
        elif sensor_type == 22:  # Motion
            if 8 <= current_hour < 22:  # Active hours
                return 0.3
            else:  # Quiet hours
                return -0.3
                
        return 0.0
    
    def _get_scenario_variation(self, sensor_type: int) -> float:
        """Get scenario-based variation for a sensor type"""
        if not self.active_scenario:
            return 0.0
            
        # Example scenarios and their effects
        scenarios = {
            'Normal Day': {
                0: 0.0,    # Normal temperature
                14: 0.0,   # Normal light
                22: 0.0    # Normal motion
            },
            'Hot Day': {
                0: 5.0,    # Higher temperature
                14: 10.0,  # Brighter
                22: -0.1   # Slightly less motion
            },
            'Cold Night': {
                0: -5.0,   # Lower temperature
                14: -20.0, # Darker
                22: -0.2   # Less motion
            },
            'Party Mode': {
                0: 2.0,    # Slightly higher temperature
                14: 20.0,  # Much brighter
                22: 0.5    # More motion
            },
            'Away Mode': {
                0: -1.0,   # Slightly lower temperature
                14: -30.0, # Darker
                22: -0.4   # Much less motion
            },
            'Morning': {
                0: -2.0,   # Cooler morning temperature
                14: 5.0,   # Gradually brightening
                22: 0.2    # Increasing motion
            }
        }
        
        if self.active_scenario in scenarios:
            variation = scenarios[self.active_scenario].get(sensor_type, 0.0)
            logger.debug(f"Scenario variation for {self.active_scenario}, sensor type {sensor_type}: {variation}")
            return variation
            
        return 0.0 

    def _initialize_simulators(self):
        # Implementation of _initialize_simulators method
        pass 

    def connect_to_broker(self):
        """Enhanced connection with automatic retries"""
        logger.info(f"Connecting to {self.broker_address}:{self.broker_port}")
        self.client.loop_stop()  # Ensure clean state
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(self.broker_address, self.broker_port)
        self.client.loop_start()  # Start network loop

    def on_connect(self, client, userdata, flags, rc):
        logger.debug(f"Connection flags: {flags}")
        logger.debug(f"Broker address: {self.broker_address}:{self.broker_port}")
        logger.debug(f"Client ID: {client._client_id}")
        if rc == 0:
            logger.success(f"Connected to {self.broker_address}:{self.broker_port}")
        else:
            logger.error(f"Connection failed to {self.broker_address}:{self.broker_port} with code {rc}")

    def on_message(self, client, userdata, msg):
        """Callback for when a message is received."""
        logger.info(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
        # Implement logic to handle incoming commands here

    def on_disconnect(self, client, userdata, rc):
        """Handle disconnections gracefully"""
        logger.warning(f"Disconnected from broker (code: {rc})")
        if rc != 0:
            logger.info("Attempting automatic reconnect...")
            self.connect_to_broker()

    def _schedule_reconnect(self):
        """Exponential backoff with jitter for reconnections"""
        max_delay = 300  # 5 minutes
        base_delay = 2
        attempt = min(self.reconnect_attempts, 10)  # Limit attempts
        
        delay = min(base_delay * (2 ** attempt), max_delay)
        jitter = random.uniform(0.5, 1.5)
        actual_delay = delay * jitter
        
        logger.info(f"Scheduling reconnect in {actual_delay:.1f}s (attempt {attempt})")
        self.reconnect_attempts += 1
        threading.Timer(actual_delay, self._perform_reconnect).start()

    def _perform_reconnect(self):
        """Safe reconnect wrapper"""
        try:
            logger.debug("Attempting MQTT reconnection...")
            self.client.reconnect()
            self.reconnect_attempts = 0
        except Exception as e:
            logger.error(f"Reconnect failed: {str(e)}")
            self._schedule_reconnect()

    def publish_sensor_data(self, sensor_id, value, sensor_type, device_name, location):
        """Thread-safe publishing"""
        with self._publish_lock:
            try:
                # Standardize topic format to lowercase with underscores
                clean_location = location.lower().replace(" ", "_")
                clean_device = device_name.lower().replace(" ", "_")
                clean_type = sensor_type.lower().replace(" ", "_")
                topic = f"smart_home/{clean_location}/{clean_device}/{clean_type}"
                
                payload = json.dumps({
                    "id": sensor_id,
                    "type": sensor_type,
                    "value": float(value),
                    "unit": self._get_unit_for_type(sensor_type),
                    "device": device_name,
                    "location": location,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                logger.info(f"📡 Publishing to {topic}") 
                logger.debug(f"Using broker: {self.broker_address}:{self.broker_port}")
                logger.debug(f"Payload: {payload}")
                logger.debug(f"Topic structure: {topic}")
                logger.debug(f"Device location: {location} | Name: {device_name}")
                
                if not self.client.is_connected():
                    logger.warning("Client not connected, reconnecting...")
                    self.connect_to_broker()
                    time.sleep(0.5)

                info = self.client.publish(topic, payload, qos=1)
                
                # Add message tracking
                self._active_messages[info.mid] = {
                    'timestamp': time.time(),
                    'topic': topic,
                    'payload': payload
                }
                
                # Cleanup old messages
                self._cleanup_message_queue()
                
                # Add UI update event
                self.event_system.emit(
                    "sensor_update",
                    {
                        "sensor_id": sensor_id,
                        "value": value,
                        "location": location,
                        "device": device_name,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
            except Exception as e:
                logger.error(f"Publish failed: {str(e)}")
                time.sleep(1)
                self.connect_to_broker()

    def _get_unit_for_type(self, sensor_type):
        unit_map = {
            "temperature": "°C",
            "humidity": "%",
            "air quality": "PPM",
            "brightness": "%",
            "color temperature": "K",
            "motion": "%",
            "door status": "Binary",
            "window status": "Binary",
            "smoke": "PPM",
            "gas": "PPM",
            "water": "Binary"
        }
        return unit_map.get(sensor_type.lower(), "")

    def start_simulation(self):
        """Starts the simulation loop."""
        self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.simulation_thread.start()

    def _simulation_loop(self):
        """Main simulation loop with proper session handling"""
        while self.running:
            try:
                with self.db() as session:
                    containers = session.query(Container).options(
                        joinedload(Container.sensors)
                    ).filter_by(is_active=True).all()
                    
                    for container in containers:
                        # Use fresh session for each container
                        with self.db() as container_session:
                            fresh_container = container_session.merge(container)
                            fresh_container.run_logic(container_session)
                            
                time.sleep(self.simulation_interval)
                
            except Exception as e:
                logger.error(f"Simulation error: {str(e)}")
                time.sleep(5)

    def stop(self):
        """Enhanced stop method with proper cleanup"""
        logger.info("Initiating shutdown sequence...")
        self.running = False
        
        if self.simulation_thread and self.simulation_thread.is_alive():
            logger.debug("Waiting for simulation thread to finish...")
            self.simulation_thread.join(timeout=10)
            
        logger.debug("Stopping MQTT client...")
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Successfully disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Error disconnecting MQTT client: {str(e)}")
            
        logger.info("SmartHomeSimulator shutdown complete")

    def _initialize_simulators(self):
        # Implementation of _initialize_simulators method
        pass 

    def on_publish(self, client, userdata, mid):
        """Callback when a message is successfully published"""
        logger.success(f"✅ Verified publish confirmation for MID: {mid}")
        logger.debug(f"Outgoing message queue: {client._out_messages}")  # Inspect internal queue

    def _cleanup_message_queue(self):
        logger.debug(f"Active messages: {len(self._active_messages)}")
        now = time.time()
        expired = [mid for mid, msg in self._active_messages.items()
                   if now - msg['timestamp'] > 30]
        for mid in expired:
            del self._active_messages[mid]

    async def get_sensor_value(self, sensor_id: int) -> float:
        """Get the current value for a sensor"""
        try:
            with self.db() as session:
                sensor = session.query(Sensor).get(sensor_id)
                if sensor:
                    return sensor.current_value
                return 0.0
        except Exception as e:
            logger.error(f"Error getting sensor value: {e}")
            return 0.0

    def start_scenario(self, container):
        """Start simulating sensors for a scenario"""
        if self.active_scenario:
            self.stop_scenario(self.active_scenario)
            
        self.active_scenario = container
        for sensor in container.sensors:
            self._start_sensor_simulation(sensor)
            
        self.event_system.emit('scenario_changed', container)

    def stop_scenario(self, container):
        """Stop simulating sensors for a scenario"""
        if self.active_scenario == container:
            for sensor in container.sensors:
                self._stop_sensor_simulation(sensor)
            self.active_scenario = None
            self.event_system.emit('scenario_changed', None)

    def _start_sensor_simulation(self, sensor):
        """Start individual sensor simulation thread"""
        if sensor.id in self.sensor_threads:
            return
            
        def simulate():
            while sensor.id in self.sensor_threads:
                # Update sensor value based on simulation logic
                sensor.simulate()
                time.sleep(sensor.interval)
                
        thread = threading.Thread(target=simulate)
        self.sensor_threads[sensor.id] = thread
        thread.start()

    def _stop_sensor_simulation(self, sensor):
        """Stop sensor simulation thread"""
        if sensor.id in self.sensor_threads:
            del self.sensor_threads[sensor.id]