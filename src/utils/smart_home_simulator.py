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
from src.database.database import db_session
from sqlalchemy.orm import joinedload
import json
import os
import subprocess
from src.models.scenario import Scenario
from src.constants.device_templates import ROOM_TEMPLATES
import asyncio

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
        if hasattr(self, '_initialized'):  # Prevent reinitialization
            return
        self._initialized = True
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
        
        # Add message tracking
        self._active_messages = {}  # Initialize message tracking dict
        
        # Connection management
        self.reconnect_attempts = 0  # Initialize reconnect counter
        self.max_reconnect_attempts = 10  # Set maximum reconnect attempts
        
        # Thread safety
        self._publish_lock = threading.Lock()
        
        # Initialize database session
        self.db = db_session
        
        # Initialize simulators after db is set
        self._initialize_simulators()
        
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
        scenarios = {
            'Normal Day': {0: 0.0, 14: 0.0, 22: 0.0},
            'Hot Day': {0: 5.0, 14: 10.0, 22: -0.1},
            # New scenarios can be added here
        }
        return scenarios.get(self.active_scenario, {}).get(sensor_type, 0.0)

    def _initialize_simulators(self):
        """Initialize simulators and initial sensor values"""
        try:
            with self.db() as session:
                devices = session.query(Device).all()
                for device in devices:
                    for sensor in device.sensors:
                        if sensor.current_value is None:
                            # Generate initial value
                            sensor.current_value = self._generate_initial_value(sensor.type)
                            session.add(sensor)
                            
                            # Prepare event data for initial value
                            sensor_data = {
                                'device_id': device.id,
                                'device_name': device.name,
                                'sensor_id': sensor.id,
                                'sensor_name': sensor.name,
                                'value': sensor.current_value,
                                'unit': sensor.unit,
                                'device_updates': device.update_counter
                            }
                            # Emit initial value
                            asyncio.create_task(self.event_system.emit('sensor_update', sensor_data))
                session.commit()
                logger.info("Initialized all sensor values")
        except Exception as e:
            logger.error(f"Error initializing simulators: {e}")

    def _generate_initial_value(self, sensor_type: str) -> float:
        """Generate initial value for a sensor based on its type"""
        initial_values = {
            "temperature": 22.0,    # Celsius
            "humidity": 50.0,       # Percentage
            "light": 500,           # Lux
            "motion": 0,            # Binary
            "air_quality": 100,     # AQI
            "co": 0.0,             # PPM
            "smoke": 0.0,          # PPM
            "gas": 0.0,            # PPM
            "water": 0             # Binary
        }
        return initial_values.get(sensor_type.lower(), 0.0)

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
        delay = min(2 ** self.reconnect_attempts, 300) * random.uniform(0.5, 1.5)
        threading.Timer(delay, self._perform_reconnect).start()

    def _perform_reconnect(self):
        try:
            self.client.reconnect()
            self.reconnect_attempts = 0
        except Exception as e:
            self._schedule_reconnect()

    def publish_sensor_data(self, topic: str, data: dict):
        """Publish sensor data to MQTT broker"""
        try:
            if not self.client.is_connected():
                logger.warning("MQTT client not connected, attempting reconnection...")
                self.connect_to_broker()
                
            # Ensure data is JSON serializable
            message = json.dumps(data)
            
            # Publish with QoS 1 to ensure delivery
            result = self.client.publish(topic, message, qos=1)
            
            # Track message for delivery confirmation
            msg_id = result[1]
            self._active_messages[msg_id] = {
                'topic': topic,
                'data': data,
                'timestamp': datetime.now()
            }
            
            if result[0] == 0:
                logger.debug(f"✅ Published to {topic}: {message}")
            else:
                logger.warning(f"🚨 Failed to publish to {topic}. Result code: {result[0]}")
                
        except Exception as e:
            logger.error(f"Error publishing sensor data: {str(e)}")

    def on_publish(self, client, userdata, mid):
        """Callback when a message is successfully published"""
        logger.success(f"✅ Verified publish confirmation for MID: {mid}")
        logger.debug(f"Outgoing message queue: {client._out_messages}")  # Inspect internal queue

    def _cleanup_message_queue(self):
        logger.debug(f"Active messages: {len(self._active_messages)}")
        now = time.time()
        expired = [mid for mid, msg in self._active_messages.items()
                   if now - msg['timestamp'].timestamp() > 30]
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

    def start_scenario(self, scenario: Scenario):
        """Start all containers in a scenario"""
        for container in scenario.containers:
            container.start()
            
    def stop_scenario(self, scenario: Scenario):
        """Stop all containers in a scenario"""
        for container in scenario.containers:
            container.stop()

    def _start_sensor_simulation(self, sensor):
        """Start individual sensor simulation thread with MQTT"""
        if sensor.id in self.sensor_threads:
            return
        
        # Create thread using the _simulate_sensor method
        thread = threading.Thread(
            target=self._simulate_sensor,
            args=(sensor,),
            daemon=True
        )
        self.sensor_threads[sensor.id] = thread
        thread.start()
        logger.debug(f"Started simulation for sensor {sensor.name}")

    def _simulate_sensor(self, sensor: Sensor):
        """Simulate sensor values with proper relationship loading"""
        try:
            with db_session() as init_session:
                # Load sensor with device and room relationships
                current_sensor = init_session.query(Sensor).options(
                    joinedload(Sensor.device).joinedload(Device.room)
                ).filter_by(id=sensor.id).one()
                
                logger.info(f"Sensor '{current_sensor.name}' (ID: {current_sensor.id}) "
                          f"mapped to device '{current_sensor.device.name if current_sensor.device else 'None'}' "
                          f"in room '{current_sensor.device.room.name if current_sensor.device and current_sensor.device.room else 'None'}")

            while True:
                with db_session() as session:
                    # Refresh with full relationships
                    current_sensor = session.query(Sensor).options(
                        joinedload(Sensor.device).joinedload(Device.room)
                    ).filter_by(id=sensor.id).one()
                    
                    # Access through fully loaded relationships
                    device = current_sensor.device
                    room = device.room if device else None
                    
                    logger.debug(f"Sensor [ID:{current_sensor.id}] hierarchy: "
                                f"{current_sensor.type} -> {device.name if device else 'None'} -> "
                                f"{room.name if room else 'None'}")
                    
                    # Rest of simulation logic using room.name instead of room_type
                    base_value = self._get_sensor_base_value(
                        current_sensor.type.lower(),
                        room.room_type if room else "default"
                    )
                    sensor_interval = current_sensor.interval

                    # Calculate and update value
                    current_value = self._calculate_sensor_value(
                        current_sensor.type.lower(), 
                        base_value,
                        room.room_type if room else "default"
                    )
                    current_sensor.current_value = current_value
                    session.commit()

                    # Prepare publish data
                    publish_data = {
                        'sensor_id': current_sensor.id,
                        'value': current_value,
                        'sensor_type': current_sensor.type,
                        'device_name': device.name if device else "Unknown",
                        'location': room.name if room else "Unknown"
                    }

                # Operations outside session context
                self.publish_sensor_data(f"sensors/{device.id}/{current_sensor.id}", publish_data)
                time.sleep(sensor_interval)

        except Exception as e:
            logger.error(f"Sensor [ID:{current_sensor.id}] error: {str(e)}")
            self._stop_sensor_simulation_by_id(current_sensor.id)

    def _calculate_sensor_value(self, sensor_type: str, base_value: float, room_type: str) -> float:
        """Calculate sensor value with validation"""
        try:
            # Validate base value
            base = float(base_value) if base_value is not None else 20.0
            
            # Add more randomness to make values change more visibly
            if sensor_type == 'temperature':
                variation = random.uniform(-3.0, 3.0) + self._get_scenario_variation(sensor_type)
                return round(base + variation, 1)
            elif sensor_type == 'humidity':
                variation = random.uniform(-8.0, 8.0)
                return max(0.0, min(100.0, base + variation))
            elif sensor_type == 'motion':
                return 1.0 if random.random() < (0.3 + self._get_scenario_variation(sensor_type)) else 0.0
            elif sensor_type in ['co', 'smoke']:
                return random.uniform(0.0, 15.0)
            elif sensor_type == 'light':
                return max(0.0, base + random.uniform(-100.0, 100.0))
            return float(base)
        except Exception as e:
            logger.warning(f"Value calculation error, using default: {str(e)}")
            return 20.0  # Fallback default

    def _stop_sensor_simulation(self, sensor):
        """Stop sensor using ID from database session"""
        with db_session() as session:
            current_sensor = session.merge(sensor)
            self._stop_sensor_simulation_by_id(current_sensor.id)

    def _stop_sensor_simulation_by_id(self, sensor_id: int):
        """Thread-safe sensor stopping by ID"""
        if sensor_id in self.sensor_threads:
            del self.sensor_threads[sensor_id]
            logger.debug(f"Stopped simulation for sensor ID: {sensor_id}")

    def start_container(self, container):
        """Start all sensors in a container"""
        logger.debug(f"Starting container {container.name} with {len(container.devices)} devices")
        for device in container.devices:
            logger.debug(f"Starting device {device.name} with {len(device.sensors)} sensors")
            for sensor in device.sensors:
                logger.debug(f"Starting sensor {sensor.name} (ID: {sensor.id})")
                self._start_sensor_simulation(sensor)
        logger.info(f"Started container {container.name} sensors")

    def stop_container(self, container):
        """Stop all sensors in a container"""
        for device in container.devices:
            for sensor in device.sensors:
                self._stop_sensor_simulation(sensor)
        logger.info(f"Stopped container {container.name} sensors")

    def _get_sensor_base_value(self, sensor_type: str, room_type: str) -> float:
        """Get base value from templates with fallback defaults"""
        try:
            # First try sensor-specific base value
            base_value = ROOM_TEMPLATES[room_type].get(f'base_{sensor_type}')
            if base_value is not None:
                return base_value
            
            # Fallback to general temperature base
            return ROOM_TEMPLATES[room_type].get('base_temperature', 20.0)
        except KeyError:
            # Default values for unknown room types
            return {
                'temperature': 20.0,
                'humidity': 50.0,
                'motion': 0.0,
                'light': 300.0,
                'co': 0.0,
                'smoke': 0.0
            }.get(sensor_type, 0.0)

    def _generate_sensor_value(self, sensor: Sensor) -> float:
        """Generate realistic sensor values based on type and previous value"""
        # Define value ranges and change rates for each sensor type
        ranges = {
            "temperature": {"min": 18.0, "max": 28.0, "change": 0.5},  # Celsius
            "humidity": {"min": 30.0, "max": 70.0, "change": 2.0},     # Percentage
            "light": {"min": 0, "max": 1000, "change": 50},            # Lux
            "motion": {"min": 0, "max": 1, "change": 1},               # Binary
            "air_quality": {"min": 0, "max": 500, "change": 10},       # AQI
            "default": {"min": 0, "max": 100, "change": 5}             # Generic
        }
        
        sensor_range = ranges.get(sensor.type, ranges["default"])
        
        if sensor.current_value is None:
            # Initial value
            return random.uniform(sensor_range["min"], sensor_range["max"])
        else:
            # Generate change based on previous value
            max_change = sensor_range["change"]
            change = random.uniform(-max_change, max_change)
            new_value = sensor.current_value + change
            
            # Ensure value stays within range
            new_value = max(sensor_range["min"], min(sensor_range["max"], new_value))
            
            # Round appropriately based on sensor type
            if sensor.type == "motion":
                new_value = round(new_value)
            elif sensor.type in ["temperature", "humidity"]:
                new_value = round(new_value, 1)
            else:
                new_value = round(new_value)
                
            return new_value

    def start_simulation(self):
        """Starts the simulation loop."""
        if not self.running:
            self.running = True
            logger.info("Starting simulation loop")
            asyncio.create_task(self._simulation_loop())
        else:
            logger.warning("Simulation already running")

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

    async def _simulation_loop(self):
        """Main simulation loop with proper session handling"""
        logger.info("Simulation loop started")
        while self.running:
            try:
                logger.debug("Running simulation iteration")
                await self._update_sensor_values()
                await asyncio.sleep(2)  # Update every 2 seconds
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error

    async def _update_sensor_values(self):
        """Update sensor values for all devices"""
        try:
            with self.db() as session:
                devices = session.query(Device).all()
                logger.debug(f"Updating {len(devices)} devices")
                
                for device in devices:
                    # Always increment counter when device is checked
                    current_count = device.update_counter or 0
                    device.update_counter = current_count + 1
                    session.add(device)
                    session.flush()  # Ensure counter is updated
                    
                    logger.debug(f"Device {device.name} counter: {device.update_counter}")
                    
                    # Prepare device update event
                    event_data = {
                        'device_id': device.id,
                        'device_name': device.name,
                        'device_updates': device.update_counter
                    }
                    
                    # Emit device update event with await
                    await self.event_system.emit('device_update', event_data)
                    logger.debug(f"Emitted device update event: {event_data}")
                    
                    # Update sensor values
                    for sensor in device.sensors:
                        # Generate new sensor value
                        new_value = self._generate_sensor_value(sensor)
                        
                        # Update sensor value
                        sensor.current_value = new_value
                        session.add(sensor)
                        
                        # Emit sensor update event
                        sensor_data = {
                            'device_id': device.id,
                            'device_name': device.name,
                            'sensor_id': sensor.id,
                            'sensor_name': sensor.name,
                            'value': sensor.current_value,
                            'unit': sensor.unit,
                            'device_updates': device.update_counter
                        }
                        # Emit sensor update with await
                        await self.event_system.emit('sensor_update', sensor_data)
                        
                        # Publish to MQTT if connected
                        if self.client and self.client.is_connected():
                            topic = f"sensors/{device.id}/{sensor.id}"
                            self.publish_sensor_data(topic, sensor_data)
                        
                        logger.debug(f"Updated {device.name} {sensor.name} to {sensor.current_value} {sensor.unit}")
                
                # Commit all changes
                session.commit()
                logger.debug("Committed all sensor and device updates")
                
        except Exception as e:
            logger.error(f"Error updating sensor values: {e}")
            if 'session' in locals():
                session.rollback()