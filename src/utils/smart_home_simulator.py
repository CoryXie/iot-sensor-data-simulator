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
from src.database.database import SessionLocal

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
    
    def __init__(self, event_system: EventSystem = None):
        """Initialize the simulator with event system"""
        # Skip if already initialized
        if SmartHomeSimulator._initialized:
            return
            
        logger.info("Initializing SmartHomeSimulator")
        self.event_system = event_system or EventSystem()
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
            region="San Francisco",
            latitude=37.7749,
            longitude=-122.4194,
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
        
        # Define sensor ranges for different sensor types
        self.sensor_ranges = {
            'temperature': {
                'min': 15.0,
                'max': 30.0,
                'base': 22.0
            },
            'humidity': {
                'min': 30.0,
                'max': 70.0,
                'base': 45.0
            },
            'light': {
                'min': 0.0,
                'max': 1000.0,
                'base': 500.0
            },
            'motion': {
                'min': 0.0,
                'max': 1.0,
                'base': 0.0
            },
            'door': {
                'min': 0.0,
                'max': 1.0,
                'base': 0.0
            },
            'window': {
                'min': 0.0,
                'max': 1.0,
                'base': 0.0
            },
            'smoke': {
                'min': 0.0,
                'max': 100.0,
                'base': 0.0
            },
            'co': {
                'min': 0.0,
                'max': 100.0,
                'base': 0.0
            },
            'air_quality': {
                'min': 0.0,
                'max': 500.0,
                'base': 50.0
            },
            'color_temp': {
                'min': 2000.0,
                'max': 6500.0,
                'base': 4000.0
            },
            'contact_sensor': {
                'min': 0.0,
                'max': 1.0,
                'base': 0.0
            },
            'status': {
                'min': 0.0,
                'max': 1.0,
                'base': 0.0
            }
        }
        
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
        """Handle client connection with proper ID handling"""
        try:
            client_id = str(client._client_id) if hasattr(client, '_client_id') else str(id(client))
            logger.debug(f"Connection flags: {flags}")
            logger.debug(f"Broker address: {self.broker_address}:{self.broker_port}")
            logger.debug(f"Client ID: {client_id}")
            if rc == 0:
                logger.success(f"Connected to {self.broker_address}:{self.broker_port}")
            else:
                logger.error(f"Connection failed to {self.broker_address}:{self.broker_port} with code {rc}")
        except Exception as e:
            logger.error(f"Error in connection handler: {str(e)}")

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
            
            # Log MQTT details before publishing
            logger.info(f"🚀 Publishing MQTT message:")
            logger.info(f"  Topic: {topic}")
            logger.info(f"  Data: {message}")
            logger.info(f"  Broker: {self.broker_address}:{self.broker_port}")
            logger.info(f"  Client Connected: {self.client.is_connected()}")
            
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
                logger.info(f"✅ Successfully published to {topic}")
                logger.debug(f"Message content: {message}")
            else:
                logger.error(f"🚨 Failed to publish to {topic}. Result code: {result[0]}")
                
        except Exception as e:
            logger.error(f"Error publishing sensor data: {str(e)}")
            logger.exception("Detailed error trace:")

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
            target=self._simulate_sensor_thread,
            args=(sensor,),
            daemon=True
        )
        self.sensor_threads[sensor.id] = thread
        thread.start()
        logger.debug(f"Started simulation for sensor {sensor.name}")

    def _simulate_sensor(self, sensor: Sensor, room_type: str = None) -> float:
        """Simulate sensor value based on environmental conditions and room type"""
        try:
            # Get room type from device's room if not provided
            if not room_type and sensor.device and sensor.device.room:
                room_type = sensor.device.room.room_type

            # Get base range for sensor type
            base_range = self.sensor_ranges.get(sensor.type, {
                'min': 0,
                'max': 100,
                'base': 50
            })

            # Get current time and weather
            current_time = datetime.now()
            weather = self.env_state.weather_condition

            # Calculate time of day factor (0-1)
            hour = current_time.hour
            time_factor = self._calculate_time_factor(hour)

            # Calculate weather impact
            weather_impact = self._calculate_weather_impact(sensor.type, weather)

            # Calculate room-specific adjustments
            room_factor = self._calculate_room_factor(room_type, sensor.type)

            # Base value calculation
            base_value = base_range['base']
            variation = random.uniform(-sensor.variation_range, sensor.variation_range)
            
            # Combine all factors
            value = base_value + (variation * room_factor * time_factor * weather_impact)

            # Ensure value is within sensor's defined range
            value = max(sensor.min_value, min(sensor.max_value, value))

            return value

        except Exception as e:
            logger.error(f"Error simulating sensor {sensor.id}: {str(e)}")
            return sensor.base_value  # Return base value as fallback

    def _calculate_room_factor(self, room_type: str, sensor_type: str) -> float:
        """Calculate room-specific adjustment factor for sensor values"""
        if not room_type:
            return 1.0

        normalized_room_type = room_type.lower().strip().replace(" ", "_")
        
        # Room-specific factors for different sensor types
        room_factors = {
            'living_room': {
                'temperature': 1.1,  # Slightly warmer
                'humidity': 0.9,     # Slightly drier
                'light': 1.2,        # Brighter
                'motion': 1.5        # More motion expected
            },
            'bedroom': {
                'temperature': 0.9,  # Slightly cooler
                'humidity': 1.0,
                'light': 0.8,        # Dimmer
                'motion': 0.7        # Less motion expected
            },
            'kitchen': {
                'temperature': 1.2,  # Warmer
                'humidity': 1.2,     # More humid
                'light': 1.1,
                'motion': 1.3
            },
            'bathroom': {
                'temperature': 1.0,
                'humidity': 1.3,     # More humid
                'light': 0.9,
                'motion': 0.8
            },
            'office': {
                'temperature': 1.0,
                'humidity': 0.9,
                'light': 1.1,
                'motion': 1.0
            },
            'garage': {
                'temperature': 0.8,  # Cooler
                'humidity': 1.1,
                'light': 0.7,        # Dimmer
                'motion': 0.6        # Less motion
            }
        }

        # Get room-specific factors or default to 1.0
        room_type_factors = room_factors.get(normalized_room_type, {})
        return room_type_factors.get(sensor_type.lower(), 1.0)

    def _calculate_time_factor(self, hour: int) -> float:
        """Calculate time of day impact factor"""
        # Define time periods
        morning = 6  # 6 AM
        noon = 12    # 12 PM
        evening = 18 # 6 PM
        night = 22   # 10 PM

        if hour >= morning and hour < noon:
            # Morning: gradual increase
            return 0.6 + (0.4 * (hour - morning) / (noon - morning))
        elif hour >= noon and hour < evening:
            # Afternoon: peak
            return 1.0
        elif hour >= evening and hour < night:
            # Evening: gradual decrease
            return 0.8 - (0.3 * (hour - evening) / (night - evening))
        else:
            # Night: lowest
            return 0.5

    def _calculate_weather_impact(self, sensor_type: str, weather: WeatherCondition) -> float:
        """Calculate weather impact factor for sensor values"""
        # Enhanced impact factors for different weather conditions
        weather_impacts = {
            'sunny': {
                'temperature': 1.4,    # Much warmer
                'humidity': 0.6,       # Much drier
                'light': 1.5,         # Much brighter
                'air_quality': 1.2    # Better air quality
            },
            'partly_cloudy': {
                'temperature': 1.2,
                'humidity': 0.8,
                'light': 1.2,
                'air_quality': 1.1
            },
            'cloudy': {
                'temperature': 0.8,    # Cooler
                'humidity': 1.2,       # More humid
                'light': 0.5,         # Much darker
                'air_quality': 0.9
            },
            'rainy': {
                'temperature': 0.7,    # Much cooler
                'humidity': 1.5,       # Much more humid
                'light': 0.3,         # Very dark
                'air_quality': 0.8
            },
            'heavy_rain': {
                'temperature': 0.6,
                'humidity': 1.7,
                'light': 0.2,
                'air_quality': 0.7
            },
            'stormy': {
                'temperature': 0.5,    # Cold
                'humidity': 1.8,       # Very humid
                'light': 0.1,         # Extremely dark
                'air_quality': 0.6
            },
            'snowy': {
                'temperature': 0.3,    # Very cold
                'humidity': 1.3,
                'light': 0.8,         # Snow reflects light
                'air_quality': 0.9
            },
            'heavy_snow': {
                'temperature': 0.2,
                'humidity': 1.4,
                'light': 0.6,
                'air_quality': 0.8
            },
            'foggy': {
                'temperature': 0.9,
                'humidity': 1.6,
                'light': 0.4,
                'air_quality': 0.7
            }
        }
        
        # Enhanced seasonal impact factors
        month = datetime.now().month
        season_impacts = {
            # Winter (Dec-Feb)
            12: {'temperature': 0.7, 'humidity': 0.9},
            1: {'temperature': 0.6, 'humidity': 0.8},
            2: {'temperature': 0.7, 'humidity': 0.9},
            
            # Spring (Mar-May)
            3: {'temperature': 0.9, 'humidity': 1.1},
            4: {'temperature': 1.0, 'humidity': 1.2},
            5: {'temperature': 1.1, 'humidity': 1.1},
            
            # Summer (Jun-Aug)
            6: {'temperature': 1.3, 'humidity': 1.0},
            7: {'temperature': 1.4, 'humidity': 1.0},
            8: {'temperature': 1.3, 'humidity': 1.1},
            
            # Fall (Sep-Nov)
            9: {'temperature': 1.1, 'humidity': 1.1},
            10: {'temperature': 0.9, 'humidity': 1.2},
            11: {'temperature': 0.8, 'humidity': 1.0}
        }

        # Get weather-specific impacts or default to neutral (1.0)
        weather_type = weather.value.lower()
        weather_type_impacts = weather_impacts.get(weather_type, {})
        impact = weather_type_impacts.get(sensor_type.lower(), 1.0)
        
        # Apply seasonal adjustment
        season_impact = season_impacts.get(month, {}).get(sensor_type.lower(), 1.0)
        impact *= season_impact
        
        # Add time-based amplification of weather effects
        hour = self.simulation_time.effective_time.hour
        if 10 <= hour <= 14:  # Peak hours
            # Amplify the deviation from neutral
            deviation = impact - 1.0
            impact = 1.0 + (deviation * 1.3)  # 30% stronger effect during peak hours
        elif 0 <= hour <= 5 or 20 <= hour <= 23:  # Night hours
            # Reduce the deviation from neutral
            deviation = impact - 1.0
            impact = 1.0 + (deviation * 0.7)  # 30% weaker effect during night
            
        # Apply outdoor temperature effect on humidity impact
        if sensor_type.lower() == 'humidity':
            # Get current outdoor temperature from environmental state
            outdoor_temp = self.env_state.temperature_celsius
            
            # Higher temperatures can reduce humidity (more evaporation)
            if outdoor_temp > 25:
                # Temperature is high, reduce humidity by up to 30%
                temp_factor = min(1.0, 1.0 - (outdoor_temp - 25) * 0.03)
                impact *= temp_factor
            elif outdoor_temp < 5:
                # Cold air holds less moisture
                impact *= max(0.7, 1.0 - (5 - outdoor_temp) * 0.03)
        
        return impact

    def update_environmental_state(
        self,
        weather: WeatherCondition,
        location: Location,
        simulation_time: SimulationTime,
        weather_data: dict = None
    ):
        """Update environmental state with weather data"""
        try:
            # If real weather data is provided, use it
            if weather_data:
                logger.info(f"Updating environmental state with real weather data: {weather_data}")
                
                # Extract key metrics from weather data
                temperature = weather_data.get('temperature')
                humidity = weather_data.get('humidity')
                
                # Create environmental state from real weather data
                self.env_state = EnvironmentalState.from_weather_data(
                    weather_data, 
                    location, 
                    simulation_time
                )
                
                # Log the update
                logger.info(f"Updated environmental state with real weather data: " 
                           f"Condition={self.env_state.weather_condition.value}, "
                           f"Temp={self.env_state.temperature_celsius}°C, "
                           f"Humidity={self.env_state.humidity_percent}%")
            else:
                # Create default environmental state
                self.env_state = EnvironmentalState(
                    weather_condition=weather,
                    location=location,
                    simulation_time=simulation_time
                )
                logger.info(f"Updated environmental state with default values: "
                           f"Condition={weather.value}, Location={location.region}")
            
            # Update current weather for simulator
            self.current_weather = self.env_state.weather_condition
            self.current_location = location
            self.simulation_time = simulation_time
            
            # Signal that environmental state has been updated
            logger.debug("Environmental state updated successfully")
        except Exception as e:
            logger.error(f"Error updating environmental state: {str(e)}")
            # Create a fallback environmental state
            self.env_state = EnvironmentalState()
            self.current_weather = self.env_state.weather_condition
            self.current_location = self.env_state.location
            self.simulation_time = self.env_state.simulation_time

    def _create_environmental_state(self) -> EnvironmentalState:
        """Create environmental state from current settings"""
        return EnvironmentalState.create_default(
            self.current_weather,
            self.simulation_time.effective_time,
            self.current_location
        )

    def _generate_sensor_value(self, sensor):
        """Generate a sensor value based on type and environmental conditions"""
        try:
            # Define base ranges for different sensor types
            base_ranges = {
                'temperature': (15, 30),  # Celsius
                'humidity': (30, 70),     # Percentage
                'light': (0, 1000),       # Lux
                'motion': (0, 1),         # Binary
                'door': (0, 1),           # Binary
                'window': (0, 1),         # Binary
                'air_quality': (0, 500),  # AQI
                'wind_speed': (0, 100),   # km/h
                'rain_rate': (0, 50),     # mm/h
                'pressure': (980, 1020),  # hPa
                'co2': (400, 2000),       # ppm
                'tvoc': (0, 1000),        # ppb
                'smoke': (0, 1),          # Binary
                'co': (0, 1),             # Binary
                'color_temp': (2700, 6500),  # Kelvin
                'contact_sensor': (0, 1),  # Binary
                'status': (0, 1),         # Binary
                'schedule': (0, 1),       # Binary (on/off)
                'position': (0, 100),     # Percentage
                'flow': (0, 10),          # L/min
                'moisture': (0, 100),     # Percentage
                'set_temperature': (16, 30),  # Celsius (HVAC setpoint)
                'power': (0, 1),          # Binary (on/off) 
                'fan_speed': (1, 5),      # Fan speed levels
                'mode': (0, 4)            # Mode settings
            }
            
            # Get base range for sensor type
            sensor_type = sensor.type.lower()
            if sensor_type not in base_ranges:
                logger.warning(f"Unknown sensor type: {sensor_type}, using temperature as default")
                base_min, base_max = base_ranges['temperature']
            else:
                base_min, base_max = base_ranges[sensor_type]
            
            # Get current value or use midpoint
            current = sensor.current_value if sensor.current_value is not None else (base_min + base_max) / 2
            
            # Get room type and indoor/outdoor status
            room_type = None
            is_indoor = True
            if sensor.device and sensor.device.room:
                room_type = sensor.device.room.room_type
                is_indoor = sensor.device.room.is_indoor
            
            # Handle binary sensors with stronger weather influence
            if sensor_type in ['motion', 'door', 'window', 'smoke', 'co', 'contact_sensor', 'status', 'schedule']:
                # Get weather impact for activity level
                weather_impact = self._calculate_weather_impact(sensor_type, self.current_weather)
                hour = self.simulation_time.effective_time.hour
                
                # Base probability heavily influenced by weather
                base_prob = 0.2 * weather_impact
                if 8 <= hour <= 22:
                    base_prob *= 2.0  # Double probability during active hours
                
                # Specific adjustments for sensor types
                if sensor_type == 'motion':
                    prob = base_prob * (2.0 if 8 <= hour <= 22 else 0.2)  # More pronounced day/night difference
                elif sensor_type in ['smoke', 'co']:
                    prob = 0.001  # Very rare activation
                elif sensor_type == 'contact_sensor':
                    prob = base_prob
                elif sensor_type == 'status':
                    prob = base_prob * 1.5
                elif sensor_type == 'schedule':
                    # For schedule, we want more stable behavior
                    # Morning and evening watering schedules for irrigation
                    if (5 <= hour <= 8) or (17 <= hour <= 20):
                        prob = 0.7  # High probability during typical watering times
                    else:
                        prob = 0.05  # Low probability during other times
                    
                    # Weather affects watering schedule
                    if self.current_weather in [WeatherCondition.RAINY, WeatherCondition.HEAVY_RAIN, WeatherCondition.STORMY]:
                        prob *= 0.2  # Much less likely to water during rain
                else:  # door/window
                    prob = base_prob
                    if not is_indoor:
                        # Much stronger weather influence on outdoor sensors
                        if self.current_weather in [WeatherCondition.STORMY, WeatherCondition.HEAVY_RAIN, WeatherCondition.HEAVY_SNOW]:
                            prob *= 0.1  # Very unlikely in severe weather
                        elif self.current_weather in [WeatherCondition.SUNNY, WeatherCondition.PARTLY_CLOUDY]:
                            prob *= 2.0  # Much more likely in nice weather
                
                # Generate value with stronger hysteresis
                if current > 0:
                    prob *= 2.0  # Higher probability to stay active if already active
                
                return 1 if random.random() < prob else 0
            
            # Handle moisture for irrigation system
            elif sensor_type == 'moisture':
                # Soil moisture level (%)
                # Get weather impact - rainy weather increases soil moisture
                weather_impact = self._calculate_weather_impact('humidity', self.current_weather)
                
                # Base moisture level
                base_moisture = 40  # Default soil moisture
                
                # Weather effects on soil moisture
                if self.current_weather in [WeatherCondition.RAINY, WeatherCondition.HEAVY_RAIN, WeatherCondition.STORMY]:
                    # Rain increases soil moisture
                    weather_modifier = 20 * weather_impact
                elif self.current_weather in [WeatherCondition.SUNNY, WeatherCondition.PARTLY_CLOUDY]:
                    # Hot/sunny weather decreases soil moisture
                    weather_modifier = -15 * (2 - weather_impact)
                else:
                    weather_modifier = 0
                
                # Calculate time-based drying effect (soil dries out over time)
                hour = self.simulation_time.effective_time.hour
                days_since_update = 0  # Placeholder for actual tracking
                drying_factor = min(30, days_since_update * 3)  # Soil dries out over days
                
                # Apply modifiers
                modified_value = base_moisture + weather_modifier - drying_factor
                
                # Add watering effect if irrigation is active
                # Check if the flow sensor for this device is showing water flow
                if sensor.device:
                    for other_sensor in sensor.device.sensors:
                        if other_sensor.type == 'flow' and other_sensor.current_value > 0:
                            modified_value += 30  # Significant increase from watering
                
                # Ensure value stays within bounds
                return max(0, min(100, modified_value))
                
            # Handle mode for various devices (HVAC, blinds, etc.)
            elif sensor_type == 'mode':
                # Mode is a discrete setting that shouldn't change on its own unless controlled by user
                # Just return the current value, or default to 0 (usually means 'Auto' mode)
                device_type = sensor.device.type if sensor.device else None
                
                # Default values for different device types
                default_modes = {
                    'hvac_system': 0,  # 0=Auto, 1=Cool, 2=Heat, 3=Fan, 4=Dry
                    'thermostat': 0,   # 0=Auto, 1=Cool, 2=Heat, 3=Fan
                    'blinds': 0,       # 0=Manual, 1=Auto, 2=Scheduled
                    'irrigation': 0     # 0=Manual, 1=Scheduled
                }
                
                # Use device-specific default or general default (0)
                default_mode = default_modes.get(device_type, 0)
                
                # Return current value or default
                return int(current if current is not None else default_mode)
                
            # Handle set temperature for HVAC/thermostat 
            elif sensor_type == 'set_temperature':
                # Set temperature is a user-controlled value that shouldn't change on its own
                # Just return the current value or a sensible default
                device_type = sensor.device.type if sensor.device else None
                
                # Default values for different device types
                default_temps = {
                    'hvac_system': 22.0,  # Central AC default temp
                    'thermostat': 21.0,   # Room thermostat default
                    'default': 22.0
                }
                
                # Use device-specific default or general default
                default_temp = default_temps.get(device_type, default_temps['default'])
                
                # Return current value or default
                return current if current is not None else default_temp
                
            # Handle power state for devices
            elif sensor_type == 'power':
                # Power is a binary on/off state
                # Just return the current value or default to off (0)
                return 1 if current == 1 else 0
                
            # Handle fan speed for HVAC
            elif sensor_type == 'fan_speed':
                # Fan speed is a user-controlled value that shouldn't change on its own
                # Default is medium (3 on a scale of 1-5)
                return int(current if current is not None else 3)
                
            # Handle water flow rate for irrigation
            elif sensor_type == 'flow':
                # Water flow depends on whether irrigation is active (controlled by schedule)
                flow_rate = 0  # Default is no flow
                
                # Check if the schedule is active for this device
                if sensor.device:
                    for other_sensor in sensor.device.sensors:
                        if other_sensor.type == 'schedule' and other_sensor.current_value == 1:
                            # Schedule is active, so water is flowing
                            flow_rate = random.uniform(2.5, 4.5)  # L/min
                
                return flow_rate
                
            # Handle color temperature with weather influence
            elif sensor_type == 'color_temp':
                hour = self.simulation_time.effective_time.hour
                weather_impact = self._calculate_weather_impact('light', self.current_weather)
                
                # Base temperature based on time of day
                if hour < 6 or hour > 18:
                    base_temp = random.uniform(2700, 3500)  # Warm white
                else:
                    base_temp = random.uniform(5000, 6500)  # Cool white
                
                # Adjust based on weather (cloudy/stormy = warmer, sunny = cooler)
                temp_adjustment = (1 - weather_impact) * 1000  # More pronounced weather effect
                return max(2700, min(6500, base_temp + temp_adjustment))
                
            # Handle position for smart blinds
            elif sensor_type == 'position':
                # Position depends on mode and light level
                position = current  # Start with current position
                
                # Check if there's a mode setting for this device
                mode = 0  # Default to manual mode
                if sensor.device:
                    for other_sensor in sensor.device.sensors:
                        if other_sensor.type == 'mode':
                            mode = int(other_sensor.current_value or 0)
                
                # Mode 0: Manual - keep current position
                # Mode 1: Auto (Light-based) - adjust based on light level and weather
                # Mode 2: Scheduled - follow time-based schedule
                
                if mode == 1:  # Auto (Light-based)
                    # Get weather and time info
                    weather_impact = self._calculate_weather_impact('light', self.current_weather)
                    hour = self.simulation_time.effective_time.hour
                    
                    # Determine target position based on light level
                    # Sunny weather = more closed blinds, cloudy = more open
                    if weather_impact > 0.7 and 9 <= hour <= 17:
                        # Bright day - close blinds more
                        target_position = 20  # Mostly closed (20% open)
                    elif weather_impact < 0.3 or hour < 7 or hour > 19:
                        # Dark conditions - open blinds
                        target_position = 90  # Mostly open
                    else:
                        # Moderate conditions
                        target_position = 50  # Half open
                    
                    # Move gradually toward target (max 10% change at a time for realism)
                    if abs(position - target_position) > 10:
                        position += 10 if target_position > position else -10
                    else:
                        position = target_position
                        
                elif mode == 2:  # Scheduled
                    hour = self.simulation_time.effective_time.hour
                    
                    # Morning schedule - open blinds
                    if 7 <= hour <= 9:
                        target_position = 80  # Mostly open
                    # Evening schedule - close blinds
                    elif 19 <= hour <= 22:
                        target_position = 10  # Mostly closed
                    # Night schedule - closed for privacy
                    elif 22 <= hour or hour < 6:
                        target_position = 0  # Fully closed
                    # Daytime schedule - partially open
                    else:
                        target_position = 60  # Partially open
                    
                    # Move gradually toward target (max 10% change at a time for realism)
                    if abs(position - target_position) > 10:
                        position += 10 if target_position > position else -10
                    else:
                        position = target_position
                
                # Ensure value stays within bounds
                return max(0, min(100, position))
            
            # Handle numeric sensors with enhanced weather impact
            else:
                # Get weather impact
                weather_impact = self._calculate_weather_impact(sensor_type, self.current_weather)
                
                # Calculate time-based variation (daily cycle)
                hour = self.simulation_time.effective_time.hour
                time_factor = math.sin((hour - 6) * math.pi / 12)  # Peak at noon
                
                # Apply weather impacts based on sensor type
                if sensor_type == 'temperature':
                    # Get outdoor temperature from environmental state
                    outdoor_temp = self.env_state.temperature_celsius
                    
                    # Check if there's an active whole home AC in the system
                    whole_home_ac = None
                    ac_settings = {}
                    
                    try:
                        with self.db() as session:
                            # Find any whole home AC device that is active
                            whole_home_ac = session.query(Device).filter(
                                Device.type == 'hvac_system',
                                Device.is_active == True
                            ).first()
                            
                            if whole_home_ac:
                                # Get AC settings from its sensors
                                for ac_sensor in whole_home_ac.sensors:
                                    ac_settings[ac_sensor.type] = ac_sensor.current_value
                    except Exception as e:
                        logger.error(f"Error checking for whole home AC: {e}")
                    
                    # Calculate realistic indoor temperature based on outdoor conditions
                    if is_indoor:
                        # Building insulation factor (0-1, higher means better insulated)
                        # Different room types have different insulation characteristics
                        insulation_factors = {
                            'living_room': 0.8,
                            'bedroom': 0.75,
                            'kitchen': 0.7,
                            'bathroom': 0.65,
                            'basement': 0.9,  # Basements are well insulated
                            'attic': 0.4,     # Attics have poor insulation
                            'garage': 0.5,    # Garages have moderate insulation
                            'hallway': 0.7,
                            'office': 0.8,
                            'default': 0.75
                        }
                        
                        # Get insulation factor based on room type
                        room_key = room_type.lower().replace(' ', '_') if room_type else 'default'
                        insulation_factor = insulation_factors.get(room_key, insulation_factors['default'])
                        
                        # Thermal lag - indoor temperature responds slowly to outdoor changes
                        # Previous value has more weight for well-insulated rooms
                        thermal_lag_factor = insulation_factor * 0.7  # 0-0.7 scale
                        
                        # Thermal transfer calculation - how much outdoor temperature affects indoor
                        outdoor_influence = 1 - insulation_factor  # Better insulation = less outdoor influence
                        
                        # Preferred indoor temperature (comfort zone)
                        preferred_temp = 22 + (time_factor * 1.5)  # 20.5°C to 23.5°C throughout the day
                        
                        # If whole home AC is active, use its set temperature as the preferred temp
                        if whole_home_ac and ac_settings.get('power', 0) == 1:
                            ac_set_temp = ac_settings.get('set_temperature')
                            ac_mode = ac_settings.get('mode', 0)
                            ac_fan_speed = ac_settings.get('fan_speed', 3)
                            
                            if ac_set_temp is not None:
                                # Mode values: 0=Auto, 1=Cool, 2=Heat, 3=Fan, 4=Dry
                                # In cooling mode (mode 1), AC works to cool the house
                                if ac_mode == 1 and outdoor_temp > ac_set_temp:
                                    preferred_temp = ac_set_temp
                                    
                                    # Fan speed affects how quickly temperature changes (1-5)
                                    # Higher fan speed means faster temperature change
                                    fan_factor = ac_fan_speed / 5.0
                                    
                                    # Increase cooling efficiency with fan speed
                                    outdoor_influence *= max(0.3, 1 - (fan_factor * 0.5))
                                    
                                    # AC can overcome some thermal lag
                                    thermal_lag_factor *= max(0.3, 1 - (fan_factor * 0.3))
                                    
                                # In heating mode (mode 2), AC works to heat the house
                                elif ac_mode == 2 and outdoor_temp < ac_set_temp:
                                    preferred_temp = ac_set_temp
                                    
                                    # Fan speed affects how quickly temperature changes
                                    fan_factor = ac_fan_speed / 5.0
                                    
                                    # Increase heating efficiency with fan speed
                                    outdoor_influence *= max(0.3, 1 - (fan_factor * 0.5))
                                    
                                    # AC can overcome some thermal lag
                                    thermal_lag_factor *= max(0.3, 1 - (fan_factor * 0.3))
                                    
                                # In auto mode (mode 0), AC works to maintain set temperature
                                elif ac_mode == 0:
                                    preferred_temp = ac_set_temp
                                    
                                    # Fan speed affects how quickly temperature changes
                                    fan_factor = ac_fan_speed / 5.0
                                    
                                    # Increase HVAC efficiency with fan speed
                                    outdoor_influence *= max(0.3, 1 - (fan_factor * 0.5))
                                    
                                    # AC can overcome some thermal lag
                                    thermal_lag_factor *= max(0.3, 1 - (fan_factor * 0.3))
                        
                        # Calculate new indoor temperature
                        # Formula: new_temp = (previous_temp * thermal_lag) + 
                        #                     (comfort_temp * (1 - outdoor_influence)) +
                        #                     (outdoor_temp * outdoor_influence * (1 - thermal_lag))
                        temperature_diff = outdoor_temp - preferred_temp
                        
                        # Start with previous temperature (thermal mass effect)
                        new_temp = current * thermal_lag_factor
                        
                        # Add influence of comfort temperature
                        new_temp += preferred_temp * (1 - thermal_lag_factor) * (1 - outdoor_influence)
                        
                        # Add influence of outdoor temperature
                        new_temp += (preferred_temp + temperature_diff * outdoor_influence) * (1 - thermal_lag_factor)
                        
                        # Apply seasonal adjustments
                        month = datetime.now().month
                        is_winter = 11 <= month or month <= 2
                        is_summer = 6 <= month <= 8
                        
                        if is_winter:
                            # Winter: Indoor tends to be warmer than outdoor, heating is active
                            if outdoor_temp < 5:
                                new_temp = max(new_temp, preferred_temp - 1)  # Heating keeps indoor temperature up
                        elif is_summer:
                            # Summer: Indoor tends to be cooler than outdoor in hot weather
                            if outdoor_temp > 28:
                                new_temp = min(new_temp, preferred_temp + 3)  # Indoor still warmer but limited
                                
                        # Limit to realistic ranges
                        modified_value = max(10, min(35, new_temp))
                    else:
                        # Outdoor temperature sensor - use environmental state with minor variations
                        local_variation = random.uniform(-1.5, 1.5)  # Local microclimate variations
                        modified_value = outdoor_temp + local_variation
                
                elif sensor_type == 'humidity':
                    # Get the actual weather humidity from environmental state
                    outdoor_humidity = self.env_state.humidity_percent
                    
                    if is_indoor:
                        # Building envelope impact on humidity transfer
                        envelope_factors = {
                            'living_room': 0.7,
                            'bedroom': 0.7,
                            'kitchen': 0.6,  # Kitchens have more moisture sources
                            'bathroom': 0.5, # Bathrooms have more moisture sources
                            'basement': 0.8, # Basements better sealed but tend to be more humid
                            'attic': 0.4,    # Attics have poor humidity control
                            'garage': 0.5,   # Garages have moderate sealing
                            'hallway': 0.7,
                            'office': 0.8,
                            'default': 0.7
                        }
                        
                        # Get building envelope factor based on room type
                        room_key = room_type.lower().replace(' ', '_') if room_type else 'default'
                        envelope_factor = envelope_factors.get(room_key, envelope_factors['default'])
                        
                        # Hour of day for activity patterns
                        hour = self.simulation_time.effective_time.hour
                        
                        # Humidity lag factor - indoor humidity changes slower than outdoor
                        humidity_lag = envelope_factor * 0.6  # 0-0.6 scale
                        
                        # Base indoor humidity calculation
                        # Start with current humidity (persistence)
                        indoor_humidity = current * humidity_lag
                        
                        # Relationship between outdoor temperature and indoor humidity
                        outdoor_temp = self.env_state.temperature_celsius
                        
                        # Calculate dew point and absolute humidity effects
                        # As outdoor temp rises relative to indoor, condensation decreases, relative humidity decreases
                        # As outdoor temp falls relative to indoor, condensation increases, relative humidity increases
                        
                        # Calculate comfortable humidity range based on temperature
                        # Higher temperatures = lower comfortable humidity
                        ideal_humidity = max(30, min(60, 80 - outdoor_temp))
                        
                        # Influence of outdoor humidity depends on temp differential and envelope
                        temp_differential = abs(outdoor_temp - (current if sensor_type == 'temperature' else 22))
                        outdoor_influence = (1 - envelope_factor) * max(0.3, 1 - (temp_differential * 0.05))
                        
                        # Add outdoor humidity influence
                        indoor_humidity += outdoor_humidity * outdoor_influence * (1 - humidity_lag)
                        
                        # Add ideal humidity influence (HVAC effect)
                        indoor_humidity += ideal_humidity * (1 - outdoor_influence) * (1 - humidity_lag)
                        
                        # Room-specific additional effects
                        if room_type:
                            if room_type.lower() == 'bathroom':
                                # Bathrooms tend to be more humid due to showers
                                shower_times = [7, 8, 9, 19, 20, 21, 22]
                                shower_factor = 25 if hour in shower_times else 5
                                indoor_humidity += shower_factor * (1 - humidity_lag)
                            elif room_type.lower() == 'kitchen':
                                # Kitchens have cooking activities
                                cooking_times = [7, 8, 12, 13, 18, 19, 20]
                                cooking_factor = 15 if hour in cooking_times else 3
                                indoor_humidity += cooking_factor * (1 - humidity_lag)
                            elif room_type.lower() == 'basement':
                                # Basements tend to be more humid due to ground contact
                                indoor_humidity += 8 * (1 - humidity_lag)
                        
                        # Weather effects on indoor humidity
                        if self.current_weather in [WeatherCondition.RAINY, WeatherCondition.HEAVY_RAIN, 
                                                  WeatherCondition.STORMY, WeatherCondition.FOGGY]:
                            # Rainy weather increases indoor humidity more
                            indoor_humidity += 5 * (1 - envelope_factor)
                        elif self.current_weather in [WeatherCondition.SUNNY, WeatherCondition.PARTLY_CLOUDY] and outdoor_temp > 25:
                            # Hot sunny days can reduce indoor humidity
                            indoor_humidity -= 3 * (1 - envelope_factor)
                        
                        # Limit to realistic range
                        modified_value = max(20, min(90, indoor_humidity))
                    else:
                        # Outdoor humidity sensor - use environmental data with minor variations
                        local_variation = random.uniform(-5, 5)  # Local variations
                        modified_value = max(10, min(100, outdoor_humidity + local_variation))
                
                # Handle other sensor types that aren't specifically handled above
                elif sensor_type == 'light':
                    # Calculate light level based on weather and time of day
                    weather_impact = self._calculate_weather_impact('light', self.current_weather)
                    
                    # Base light level based on time of day
                    hour = self.simulation_time.effective_time.hour
                    if 7 <= hour <= 19:  # Daytime
                        base_light = 600 * weather_impact  # Full daylight affected by weather
                    elif hour < 5 or hour > 21:  # Night
                        base_light = 50  # Low ambient light at night
                    else:  # Dawn/dusk
                        base_light = 250 * weather_impact  # Intermediate level
                    
                    # Adjust for indoor vs outdoor
                    if is_indoor:
                        # Indoor light is reduced
                        base_light *= 0.3
                        
                        # Room-specific adjustments
                        if room_type:
                            if room_type.lower() in ['bathroom', 'hallway', 'bedroom']:
                                base_light *= 0.7  # Darker rooms
                            elif room_type.lower() in ['kitchen', 'living_room', 'office']:
                                base_light *= 1.2  # Brighter rooms
                    
                    # Add randomness
                    modified_value = base_light * (0.8 + 0.4 * random.random())
                    
                elif sensor_type == 'air_quality':
                    # Air quality (AQI) - lower is better
                    weather_impact = self._calculate_weather_impact('air_quality', self.current_weather)
                    outdoor_aqi = 50 * (2 - weather_impact)  # Weather affects outdoor AQI
                    
                    if is_indoor:
                        # Indoor air quality is generally better than outdoor
                        modified_value = outdoor_aqi * 0.7
                        
                        # Room-specific adjustments
                        if room_type:
                            if room_type.lower() in ['kitchen']:
                                modified_value *= 1.3  # Kitchen can have worse air quality (cooking)
                            elif room_type.lower() in ['bathroom']:
                                modified_value *= 1.1  # Slightly worse
                    else:
                        modified_value = outdoor_aqi
                        
                elif sensor_type == 'pressure':
                    # Atmospheric pressure (hPa)
                    # Base pressure level (normal sea level pressure)
                    base_pressure = 1013.25
                    
                    # Weather influence on pressure
                    if self.current_weather in [WeatherCondition.STORMY, WeatherCondition.HEAVY_RAIN]:
                        # Low pressure during storms
                        pressure_mod = -15
                    elif self.current_weather in [WeatherCondition.SUNNY, WeatherCondition.PARTLY_CLOUDY]:
                        # High pressure during fair weather
                        pressure_mod = 10
                    else:
                        pressure_mod = 0
                        
                    # Random variation
                    variation = random.uniform(-5, 5)
                    
                    # Indoor pressure matches outdoor, but with less variation
                    if is_indoor:
                        modified_value = base_pressure + (pressure_mod * 0.3) + (variation * 0.3)
                    else:
                        modified_value = base_pressure + pressure_mod + variation
                        
                elif sensor_type == 'co2':
                    # CO2 levels (ppm)
                    # Outdoor baseline (~ 400 ppm)
                    outdoor_co2 = 400
                    
                    if is_indoor:
                        # Indoor CO2 levels are higher
                        base_co2 = 600
                        
                        # Room-specific and time-based adjustments
                        hour = self.simulation_time.effective_time.hour
                        occupancy_factor = 1.0
                        
                        # Higher CO2 when rooms are likely occupied
                        if 8 <= hour <= 22:
                            occupancy_factor = 1.5
                            
                        if room_type:
                            if room_type.lower() in ['bedroom'] and (0 <= hour <= 7 or 22 <= hour <= 23):
                                # High CO2 in bedrooms at night when people sleep
                                occupancy_factor = 2.0
                            elif room_type.lower() in ['living_room', 'kitchen'] and (17 <= hour <= 21):
                                # High CO2 in living areas during evening
                                occupancy_factor = 1.8
                        
                        modified_value = base_co2 * occupancy_factor + random.uniform(-50, 50)
                    else:
                        # Outdoor CO2 is relatively stable
                        modified_value = outdoor_co2 + random.uniform(-20, 20)
                        
                else:
                    # Default handling for any other numeric sensor type
                    # Use the weather impact as a modifier on the current value
                    weather_impact = self._calculate_weather_impact(sensor_type, self.current_weather)
                    base_value = (base_min + base_max) / 2  # Use the midpoint of the range
                    
                    # Calculate a modifier based on weather impact
                    weather_modifier = (weather_impact - 1.0) * 0.2 * (base_max - base_min)
                    
                    # Calculate time-based variation
                    hour = self.simulation_time.effective_time.hour
                    time_modifier = math.sin((hour - 6) * math.pi / 12) * 0.1 * (base_max - base_min)
                    
                    # Apply modifiers to the base value
                    modified_value = base_value + weather_modifier + time_modifier
                    
                    # Ensure value stays within the defined range
                    modified_value = max(base_min, min(base_max, modified_value))
                
                # Add small random variation (±5%)
                variation = random.uniform(-0.05, 0.05) * modified_value
                final_value = modified_value + variation
                
                # Ensure value stays within bounds
                final_value = max(base_min, min(base_max, final_value))
                
                # Round based on sensor type
                if sensor_type in ['temperature']:
                    final_value = round(final_value, 1)
                elif sensor_type in ['humidity', 'light', 'air_quality', 'wind_speed', 'rain_rate']:
                    final_value = round(final_value, 0)
                else:
                    final_value = round(final_value, 2)
                
                return final_value
                
        except Exception as e:
            logger.error(f"Error generating sensor value: {str(e)}")
            return sensor.current_value or (base_min + base_max) / 2  # Return current value or midpoint

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
        logger.info("🔄 Simulation loop started")
        while self.running:
            try:
                logger.info("⏱️ Running simulation iteration")
                with SessionLocal() as session:
                    # Query devices with their sensors
                    devices = session.query(Device).options(
                        joinedload(Device.sensors)
                    ).all()
                    
                    logger.info(f"📊 Processing {len(devices)} devices")
                    
                    for device in devices:
                        try:
                            device_updated = False
                            logger.info(f"🔍 Processing device: {device.name} with {len(device.sensors)} sensors")
                            
                            # Get device type and location
                            device_type = device.type.lower().replace(" ", "_")
                            location = None
                            if device.room:
                                location = device.room.room_type.lower().replace(" ", "_")
                            
                            # Map device types to categories
                            device_category = {
                                'environmental_monitor': 'sensor_hub',
                                'light_control': 'lighting',
                                'security_system': 'security_system',
                                'safety_monitor': 'safety'
                            }.get(device_type, device_type)
                            
                            # Update sensor values
                            for sensor in device.sensors:
                                # Merge sensor with current session
                                sensor = session.merge(sensor)
                                
                                # Generate new sensor value
                                new_value = self._generate_sensor_value(sensor)
                                
                                # Only update if value has changed significantly
                                if sensor.current_value is None or abs(new_value - sensor.current_value) > 0.01:
                                    old_value = sensor.current_value
                                    sensor.current_value = new_value
                                    session.add(sensor)
                                    device_updated = True
                                    
                                    # Create sensor data payload
                                    sensor_data = {
                                        'id': sensor.id,
                                        'name': sensor.name or f'sensor_{sensor.id}',
                                        'type': sensor.type,
                                        'value': new_value,
                                        'unit': sensor.unit,
                                        'timestamp': datetime.now().isoformat(),
                                        'device_id': sensor.device_id,
                                        'location': location,
                                        'weather': self.env_state.weather_condition.value,
                                        'region': self.env_state.location.region,
                                        'previous_value': old_value
                                    }
                                    
                                    # Log sensor update
                                    logger.info(f"📡 Sensor update - {sensor.name}: {new_value} {sensor.unit}")
                                    
                                    # Publish to MQTT with updated topic structure
                                    if location and device_category:
                                        # Create MQTT topic with the new structure
                                        topic = f"smart_home/{location}/{device_category}/{sensor.type.lower()}"
                                        self.publish_sensor_data(topic, sensor_data)
                                        
                                        # Emit event for UI update
                                        await self.event_system.emit('sensor_update', {
                                            'sensor_id': sensor.id,
                                            'value': new_value,
                                            'unit': sensor.unit,
                                            'timestamp': datetime.now().isoformat(),
                                            'device_id': device.id,
                                            'device_name': device.name,
                                            'location': location,
                                            'device_type': device_category
                                        })
                            
                            # Increment device update counter if any sensor was updated
                            if device_updated:
                                device.update_counter += 1
                                session.add(device)
                                
                                # Emit device update event for UI
                                await self.event_system.emit('device_update', {
                                    'device_id': device.id,
                                    'name': device.name,
                                    'type': device_category,
                                    'location': location,
                                    'update_counter': device.update_counter
                                })
                            
                            # Commit changes for each device's sensors
                            session.commit()
                            
                        except Exception as e:
                            logger.error(f"Error processing device {device.name}: {str(e)}")
                            session.rollback()
                            continue
                    
                await asyncio.sleep(self.simulation_interval)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error

    async def update_weather_forecast(self, location: Location):
        """Update weather forecast data with real-time weather information"""
        try:
            logger.info(f"Fetching real weather data for location: {location.region} ({location.latitude}, {location.longitude})")
            
            # Create location query for the weather API
            location_query = LocationQuery(
                type=LocationType.LATLON,
                value=(location.latitude, location.longitude)
            )
            
            # Initialize weather service if not already done
            if not hasattr(self, 'weather_service'):
                from src.services.weather_service import WeatherService
                self.weather_service = WeatherService()
                logger.info("Initialized Weather Service")
            
            # Get current weather data asynchronously
            weather_data = None
            try:
                # First try using the async method if available
                if hasattr(self.weather_service, 'get_weather_async'):
                    weather_data = await self.weather_service.get_weather_async(location_query)
                else:
                    # Fall back to synchronous method in a thread pool
                    import functools
                    weather_data = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        functools.partial(self.weather_service.get_weather, location_query)
                    )
            except Exception as e:
                logger.error(f"Error fetching weather data: {str(e)}")
                
            if weather_data:
                logger.info(f"Weather data received: {weather_data.get('description', 'No description')}, "
                           f"Temperature: {weather_data.get('temperature')}°C, "
                           f"Humidity: {weather_data.get('humidity')}%")
                
                # Map API weather condition to our enum
                weather_condition = weather_data.get('weather_condition', self.current_weather)
                
                # Get the local time for the selected region
                try:
                    # Import pytz for timezone handling if available
                    import pytz
                    from datetime import datetime
                    
                    # Try to get the timezone from the location object
                    timezone_str = location.timezone
                    if not timezone_str:
                        # Default to a timezone based on longitude if not specified
                        # This is a rough approximation - better to have the actual timezone
                        from timezonefinder import TimezoneFinder
                        tf = TimezoneFinder()
                        timezone_str = tf.timezone_at(lat=location.latitude, lng=location.longitude)
                        
                    if timezone_str:
                        # Get the timezone object
                        timezone = pytz.timezone(timezone_str)
                        
                        # Get the current time in that timezone
                        local_time = datetime.now(timezone)
                        logger.info(f"Local time in {location.region}: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                        
                        # Update simulation time with the local time
                        self.simulation_time = SimulationTime(local_time)
                        logger.info(f"Updated simulation time to match {location.region} local time")
                    else:
                        logger.warning(f"Could not determine timezone for {location.region}, using system time")
                        self.simulation_time = SimulationTime(datetime.now())
                except ImportError as e:
                    logger.warning(f"Could not import timezone libraries, using system time: {str(e)}")
                    self.simulation_time = SimulationTime(datetime.now())
                except Exception as e:
                    logger.error(f"Error determining local time for {location.region}: {str(e)}")
                    self.simulation_time = SimulationTime(datetime.now())
                
                # Update environmental state with actual weather data and local time
                self.update_environmental_state(
                    weather_condition,
                    location,
                    self.simulation_time,
                    weather_data
                )
                
                # Update current weather to match real weather data
                self.current_weather = weather_condition
                logger.info(f"Updated current weather to {weather_condition.value} based on real weather data")
                
                # Update all sensors to reflect the new environmental conditions
                await self.refresh_all_sensor_values()
                
                # Get forecast data if method is available
                if hasattr(self.weather_service, 'get_forecast'):
                    try:
                        forecast = await asyncio.get_event_loop().run_in_executor(
                            None, 
                            functools.partial(self.weather_service.get_forecast, location_query)
                        )
                        if forecast:
                            logger.info(f"Forecast data received for {len(forecast)} periods")
                            # Store forecast data for future use
                            self.weather_forecast = forecast
                    except Exception as e:
                        logger.error(f"Error fetching forecast data: {str(e)}")
                
                return True
            else:
                logger.warning(f"No weather data received for {location.region}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating weather forecast: {str(e)}")
            return False
            
    async def refresh_all_sensor_values(self):
        """Refresh all sensor values to reflect updated environmental conditions"""
        try:
            # Get all active sensors
            with SessionLocal() as session:
                active_sensors = session.query(Sensor).all()
                
            # Update each sensor with new environmental conditions
            for sensor in active_sensors:
                # Only update if the sensor is being simulated
                if sensor.id in self.sensor_threads:
                    try:
                        # Generate new value based on updated environmental state
                        new_value = self._generate_sensor_value(sensor)
                        
                        # Update sensor value
                        with SessionLocal() as session:
                            db_sensor = session.query(Sensor).filter_by(id=sensor.id).first()
                            if db_sensor:
                                db_sensor.current_value = new_value
                                session.commit()
                                logger.debug(f"Updated sensor {sensor.name} value to {new_value}")
                    except Exception as e:
                        logger.error(f"Error updating sensor {sensor.name}: {str(e)}")
                        
            logger.info(f"Refreshed values for all active sensors based on new weather data")
            return True
        except Exception as e:
            logger.error(f"Error refreshing sensor values: {str(e)}")
            return False

    def get_weather_adjusted_value(self, base_value: float, sensor_type: str, env_state: EnvironmentalState) -> float:
        """Get weather-adjusted sensor value"""
        # Get weather impact factors
        impact_factors = WeatherImpactFactors.get_impact_factors(
            env_state.weather,
            env_state.temperature_celsius,
            env_state.humidity_percent
        )
        
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

    def _simulate_sensor_thread(self, sensor):
        """Thread function to simulate sensor data over time"""
        with SessionLocal() as session:
            while self.running and sensor.id in self.sensor_threads:
                try:
                    # Merge sensor with current session to ensure persistence
                    sensor = session.merge(sensor)
                    session.refresh(sensor)
                    
                    # Get location from device's room
                    location = None
                    if sensor.device and sensor.device.room:
                        location = sensor.device.room.room_type
                    
                    if not location:
                        logger.warning(f"Sensor {sensor.id} ({sensor.name}) has no location")
                        time.sleep(self.simulation_interval)
                        continue
                    
                    # Simulate sensor value
                    value = self._simulate_sensor(sensor, location)
                    
                    # Update the sensor's current value
                    sensor.current_value = value
                    session.add(sensor)
                    session.commit()  # Commit changes to ensure persistence
                    
                    # Create sensor data payload
                    sensor_data = {
                        'id': sensor.id,
                        'name': sensor.name or f'sensor_{sensor.id}',
                        'type': sensor.type,
                        'value': value,
                        'unit': sensor.unit,
                        'timestamp': datetime.now().isoformat(),
                        'device_id': sensor.device_id,
                        'location': location,
                        'weather': self.env_state.weather_condition.value,
                        'region': self.env_state.location.region
                    }
                    
                    # Log sensor data before publishing
                    logger.info(f"📊 Generated sensor data for {sensor.name} (ID: {sensor.id}):")
                    logger.info(f"  Value: {value} {sensor.unit}")
                    logger.info(f"  Location: {location}")
                    logger.info(f"  Weather: {self.env_state.weather_condition.value}")
                    
                    # Publish to MQTT with updated topic structure
                    if location and sensor.device:
                        device_type = sensor.device.type if hasattr(sensor.device, 'type') else 'unknown'
                        topic = f"smart_home/{location}/{device_type}/{sensor.type}"
                        self.publish_sensor_data(topic, sensor_data)
                    
                    # Sleep for simulation interval
                    time.sleep(self.simulation_interval)
                    
                except Exception as e:
                    logger.error(f"Error simulating sensor {sensor.id}: {str(e)}")
                    logger.exception("Detailed error trace:")
                    session.rollback()  # Rollback on error
                    time.sleep(self.simulation_interval)

    def set_ac_parameters(self, power: bool, temperature: float, mode: int, fan_speed: int):
        """
        Set parameters for the whole home AC system
        
        Args:
            power: True if AC is on, False if off
            temperature: Target temperature in Celsius
            mode: 0=Auto, 1=Cool, 2=Heat, 3=Fan, 4=Dry
            fan_speed: Fan speed from 1-5
        """
        try:
            with self.db() as session:
                # Find the whole home AC device
                ac_device = session.query(Device).filter(
                    Device.type == 'hvac_system'
                ).first()
                
                if not ac_device:
                    logger.warning("No whole home AC found in the system")
                    return False
                
                # Set the device to active based on power setting
                ac_device.is_active = power
                
                # Update the sensor values
                for sensor in ac_device.sensors:
                    if sensor.type == 'power':
                        sensor.current_value = 1 if power else 0
                    elif sensor.type == 'set_temperature' and power:
                        sensor.current_value = max(16, min(30, temperature))
                    elif sensor.type == 'mode' and power:
                        sensor.current_value = max(0, min(4, mode))
                    elif sensor.type == 'fan_speed' and power:
                        sensor.current_value = max(1, min(5, fan_speed))
                
                # Increment update counter
                ac_device.update_counter += 1
                
                # Commit changes
                session.add(ac_device)
                session.commit()
                
                # Log the change
                logger.info(f"Updated whole home AC: Power={'On' if power else 'Off'}, "
                           f"Temp={temperature}°C, Mode={mode}, Fan={fan_speed}")
                
                # Emit device update event
                asyncio.create_task(self.event_system.emit('device_update', {
                    'device_id': ac_device.id,
                    'name': ac_device.name,
                    'type': 'hvac_system',
                    'power': power,
                    'temperature': temperature,
                    'mode': mode,
                    'fan_speed': fan_speed,
                    'update_counter': ac_device.update_counter
                }))
                
                return True
                
        except Exception as e:
            logger.error(f"Error setting AC parameters: {e}")
            return False
    
    # Method to control smart thermostat
    def set_thermostat(self, room_id: int, power: bool, temperature: float, mode: int):
        """
        Set parameters for a room thermostat
        
        Args:
            room_id: ID of the room where the thermostat is located
            power: True if thermostat is on, False if off
            temperature: Target temperature in Celsius
            mode: 0=Auto, 1=Cool, 2=Heat, 3=Fan
        """
        try:
            with self.db() as session:
                # Find the thermostat in the specified room
                thermostat = session.query(Device).filter(
                    Device.type == 'thermostat',
                    Device.room_id == room_id
                ).first()
                
                if not thermostat:
                    logger.warning(f"No thermostat found in room {room_id}")
                    return False
                
                # Set the device to active based on power setting
                thermostat.is_active = power
                
                # Update the sensor values
                for sensor in thermostat.sensors:
                    if sensor.type == 'power':
                        sensor.current_value = 1 if power else 0
                    elif sensor.type == 'set_temperature' and power:
                        sensor.current_value = max(16, min(30, temperature))
                    elif sensor.type == 'mode' and power:
                        sensor.current_value = max(0, min(3, mode))
                
                # Increment update counter
                thermostat.update_counter += 1
                
                # Commit changes
                session.add(thermostat)
                session.commit()
                
                # Log the change
                logger.info(f"Updated thermostat in room {room_id}: Power={'On' if power else 'Off'}, "
                           f"Temp={temperature}°C, Mode={mode}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error setting thermostat parameters: {e}")
            return False
            
    # Method to control smart blinds
    def set_blinds(self, room_id: int, position: int, mode: int):
        """
        Set parameters for smart blinds
        
        Args:
            room_id: ID of the room where the blinds are located
            position: Position from 0 (closed) to 100 (open)
            mode: 0=Manual, 1=Auto (light-based), 2=Scheduled
        """
        try:
            with self.db() as session:
                # Find the blinds in the specified room
                blinds = session.query(Device).filter(
                    Device.type == 'blinds',
                    Device.room_id == room_id
                ).first()
                
                if not blinds:
                    logger.warning(f"No smart blinds found in room {room_id}")
                    return False
                
                # Update the sensor values
                for sensor in blinds.sensors:
                    if sensor.type == 'position':
                        sensor.current_value = max(0, min(100, position))
                    elif sensor.type == 'mode':
                        sensor.current_value = max(0, min(2, mode))
                
                # Increment update counter
                blinds.update_counter += 1
                
                # Commit changes
                session.add(blinds)
                session.commit()
                
                # Log the change
                logger.info(f"Updated blinds in room {room_id}: Position={position}%, Mode={mode}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error setting blinds parameters: {e}")
            return False