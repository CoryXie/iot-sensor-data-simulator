import random
from datetime import datetime, timezone
from typing import Dict, Optional
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
from src.models.environmental_factors import WeatherCondition, EnvironmentalState, Location, SimulationTime, get_sensor_value_modifier, WeatherImpactFactors
import asyncio
import math
from src.services.weather_service import WeatherService, LocationQuery, LocationType

class SmartHomeSimulator:
    """Class to handle smart home sensor value simulation"""
    
    _instance = None
    _initialized = False
    
    @classmethod
    def get_instance(cls, event_system: EventSystem = None):
        """Get or create singleton instance"""
        if not cls._instance:
            cls._instance = cls(event_system)
        return cls._instance
    
    def __init__(self, event_system: EventSystem):
        """Initialize the simulator with event system"""
        # Skip if already initialized
        if SmartHomeSimulator._initialized:
            return
            
        logger.info("Initializing SmartHomeSimulator")
        self.event_system = event_system
        self.active_scenario = None
        self.sensor_threads = {}
        self.base_values = {}
        self.device_simulators = {}
        self.sensor_simulators = {}
        self.weather_forecast = {}  # Store weather forecast data
        self.broker_address = os.getenv('MQTT_BROKER_ADDRESS', 'localhost')
        self.broker_port = int(os.getenv('MQTT_BROKER_PORT', 1883))
        self.simulation_interval = 5
        
        # Initialize weather service
        self.weather_service = WeatherService()
        
        # Environmental state
        self.current_weather = WeatherCondition.SUNNY
        self.current_location = Location(
            country="United States",
            region="San Francisco",
            timezone="America/Los_Angeles"
        )
        self.simulation_time = SimulationTime(datetime.now())
        self.env_state = self._create_environmental_state()
        
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
        
        SmartHomeSimulator._initialized = True
    
    def is_running(self):
        """Check if simulation is running"""
        return self.running
    
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
        """Simulate sensor readings"""
        with self.db() as session:
            while self.running and sensor.id in self.sensor_threads:
                try:
                    # Refresh sensor to ensure relationships are loaded
                    session.refresh(sensor)
                    
                    # Get location from container or room
                    location = None
                    if sensor.container_id:
                        container = session.query(Container).get(sensor.container_id)
                        if container:
                            location = container.location
                    elif sensor.room_id:
                        room = session.query(Room).get(sensor.room_id)
                        if room:
                            location = room.room_type
                        
                    if not location:
                        logger.warning(f"Sensor {sensor.id} ({sensor.name}) has no location")
                        time.sleep(self.simulation_interval)
                        continue
                        
                    # Rest of simulation logic...
                    if not hasattr(sensor, '_simulator'):
                        sensor._simulator = self._create_simulator(sensor)

                    value = sensor._simulator.next_value()
                    
                    # Update the sensor's current value
                    sensor.current_value = value
                    session.add(sensor)
                    
                    # Create sensor data payload
                    sensor_data = {
                        'id': sensor.id,
                        'name': sensor.name or f'sensor_{sensor.id}',
                        'type': sensor.type,
                        'value': value,
                        'unit': sensor.unit,
                        'timestamp': self.simulation_time.effective_time.isoformat(),
                        'device_id': sensor.device_id,
                        'location': location,
                        'weather': self.current_weather.value,
                        'region': self.current_location.region
                    }
                    
                    # Publish to MQTT
                    self._publish_sensor_data(sensor_data)
                    
                    # Sleep for simulation interval
                    time.sleep(self.simulation_interval)
                    
                except Exception as e:
                    logger.error(f"Error simulating sensor {sensor.id}: {str(e)}")
                    time.sleep(self.simulation_interval)

    def update_environmental_state(
        self,
        weather: WeatherCondition,
        location: Location,
        simulation_time: SimulationTime
    ):
        """Update environmental state with new conditions"""
        self.current_weather = weather
        self.current_location = location
        self.simulation_time = simulation_time
        self.env_state = self._create_environmental_state()
        logger.info(
            f"Updated environmental state: {location.region}, {weather.value}, "
            f"Time: {simulation_time.effective_time.strftime('%H:%M')}"
        )

    def _create_environmental_state(self) -> EnvironmentalState:
        """Create environmental state from current settings"""
        return EnvironmentalState.create_default(
            self.current_weather,
            self.simulation_time.effective_time,
            self.current_location
        )

    def _generate_sensor_value(self, sensor: Sensor) -> float:
        """Generate a sensor value based on sensor type and environmental conditions"""
        base_ranges = {
            'temperature': (18, 25),  # Celsius
            'humidity': (30, 60),     # Percent
            'light': (0, 100),        # Percent
            'motion': (0, 1),         # Binary
            'air_quality': (0, 100),  # AQI
            'pressure': (980, 1020),  # hPa
            'noise': (30, 70),        # dB
            'water_level': (0, 100),  # Percent
            'smoke': (0, 50),         # PPM
            'co2': (400, 1000),       # PPM
        }
        
        sensor_type = sensor.type.lower()
        if sensor_type not in base_ranges:
            sensor_type = 'temperature'  # Default to temperature if type not found
            
        base_min, base_max = base_ranges[sensor_type]
        
        # Get environmental modifier
        env_modifier = get_sensor_value_modifier(self.env_state, sensor_type)
        
        # Generate base value
        base_value = random.uniform(base_min, base_max)
        
        # Apply environmental modifier
        modified_value = base_value * env_modifier
        
        # Add time-based variations
        if sensor_type in ['temperature', 'humidity', 'light']:
            time_variation = self._get_time_based_variation(sensor_type)
            modified_value += time_variation
        
        # Ensure value stays within reasonable bounds
        return max(base_min, min(base_max, modified_value))

    def _get_time_based_variation(self, sensor_type: str) -> float:
        """Get time-based variation for sensor values"""
        hour = self.simulation_time.effective_time.hour
        
        if sensor_type == 'temperature':
            # Temperature peaks in afternoon, lowest at night
            return 5 * math.sin((hour - 6) * math.pi / 12)  # Peak at 15:00
            
        elif sensor_type == 'humidity':
            # Humidity highest in early morning, lowest in afternoon
            return -10 * math.sin((hour - 6) * math.pi / 12)  # Peak at 03:00
            
        elif sensor_type == 'light':
            # Light follows sun pattern
            if 6 <= hour <= 18:  # Daytime
                return 20 * math.sin((hour - 6) * math.pi / 12)  # Peak at noon
            return 0  # Night time
            
        return 0.0

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
                            # Get device attributes with fallbacks
                            device_name = device.name or f"device_{device.id}"
                            device_location = device.location or device.room.name if device.room else "unknown"
                            sensor_name = sensor.name or f"sensor_{sensor.id}"
                            
                            # Format the topic components
                            device_name = device_name.lower().replace(' ', '_')
                            location = device_location.lower().replace(' ', '_')
                            sensor_type = sensor_name.lower().replace(' ', '_')
                            
                            # Format the topic
                            topic = f"smart_home/{location}/{device_name}/{sensor_type}"
                            
                            # Format the message data
                            message_data = {
                                "id": sensor.id,
                                "type": sensor_name,
                                "value": sensor.current_value,
                                "unit": sensor.unit or "",
                                "device": device_name,
                                "location": device_location,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            # Log the topic for debugging
                            logger.debug(f"Publishing to MQTT topic: {topic}")
                            self.publish_sensor_data(topic, message_data)
                        
                        logger.debug(f"Updated {device.name} {sensor.name} to {sensor.current_value} {sensor.unit}")
                
                # Commit all changes
                session.commit()
                logger.debug("Committed all sensor and device updates")
                
        except Exception as e:
            logger.error(f"Error updating sensor values: {e}")
            if 'session' in locals():
                session.rollback()

    async def update_weather_forecast(self, location: Location):
        """Update weather forecast data"""
        try:
            # Get 3-day forecast
            forecast = await self.weather_service.get_forecast(
                LocationQuery(
                    type=LocationType.CITY,
                    value=f"{location.region}, {location.country}"
                ),
                days=3
            )
            
            if forecast:
                self.weather_forecast = forecast
                logger.info(f"Updated weather forecast for {location.region}, {location.country}")
                
                # Notify event system about weather update
                await self.event_system.emit_event(
                    "weather_forecast_updated",
                    {"forecast": forecast}
                )
        except Exception as e:
            logger.error(f"Failed to update weather forecast: {e}")

    def get_weather_adjusted_value(self, base_value: float, sensor_type: str, env_state: EnvironmentalState) -> float:
        """Get weather-adjusted sensor value"""
        # Get weather impact factors
        impact_factors = WeatherImpactFactors.get_impact_factors(env_state.weather)
        
        # Apply specific modifiers based on sensor type
        if sensor_type == "temperature":
            return base_value + impact_factors.temperature_modifier
        elif sensor_type == "humidity":
            return min(100, max(0, base_value + impact_factors.humidity_modifier))
        elif sensor_type == "light":
            return min(100, max(0, base_value + impact_factors.light_level_modifier))
        elif sensor_type == "air_quality":
            return base_value + impact_factors.air_quality_modifier
        elif sensor_type == "noise":
            return base_value + impact_factors.noise_level_modifier
        
        return base_value

    async def simulate_sensor_values(self, sensor: Sensor, env_state: EnvironmentalState) -> Dict:
        """Simulate sensor values based on type and environmental conditions"""
        base_value = self.base_values.get(sensor.id, self._get_base_value(sensor.type))
        
        # Get time-based modifier
        time_modifier = get_sensor_value_modifier(env_state, sensor.type)
        
        # Apply weather adjustments
        weather_adjusted = self.get_weather_adjusted_value(base_value, sensor.type, env_state)
        
        # Apply time modifier
        final_value = weather_adjusted * time_modifier
        
        # Add some random variation (±5%)
        variation = random.uniform(-0.05, 0.05) * final_value
        final_value += variation
        
        # Ensure values stay within reasonable bounds
        if sensor.type in ["humidity", "light"]:
            final_value = min(100, max(0, final_value))
        
        # Store the new base value for next iteration
        self.base_values[sensor.id] = final_value
        
        # Prepare sensor data
        sensor_data = {
            "sensor_id": sensor.id,
            "type": sensor.type,
            "value": round(final_value, 2),
            "unit": sensor.unit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": sensor.location,
            "environmental_conditions": {
                "weather": env_state.weather.value,
                "temperature": env_state.temperature_celsius,
                "humidity": env_state.humidity_percent,
                "light_level": env_state.light_level_percent
            }
        }
        
        return sensor_data