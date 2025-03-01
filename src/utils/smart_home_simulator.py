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
        self.simulation_interval = 2  # Reduced from 5 seconds to 2 seconds for more frequent updates
        
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
        
        self.preferred_temperature = 20.0  # Default preferred temperature
        
        SmartHomeSimulator._initialized = True
    
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
            outdoor_temp = self.env_state.temperature_celsius  # Access temperature from EnvironmentalState
            outdoor_humidity = self.env_state.humidity_percent  # Access humidity from EnvironmentalState

            # Calculate time of day factor (0-1)
            hour = current_time.hour
            time_factor = self._calculate_time_factor(hour)

            # Calculate weather impact
            weather_impact = self._calculate_weather_impact(sensor.type, self.env_state.weather_condition)

            # Calculate room-specific adjustments
            room_factor = self._calculate_room_factor(room_type, sensor.type)

            # Base value calculation
            base_value = base_range['base']

            # Adjust base value for temperature sensor if AC is active
            if sensor.type == 'temperature' and self.preferred_temperature is not None:
                # Gradually adjust towards preferred temperature
                current_temp = base_value  # Assuming base_value is the current temperature
                rate_of_change = 0.5  # Degrees per minute
                time_elapsed = 1  # Assuming this method is called every minute
                change = rate_of_change * time_elapsed
                if current_temp < self.preferred_temperature:
                    base_value = min(current_temp + change, self.preferred_temperature)
                elif current_temp > self.preferred_temperature:
                    base_value = max(current_temp - change, self.preferred_temperature)

            # Combine outdoor temperature into the final value
            if sensor.type == 'temperature':
                # Adjust the base value based on outdoor temperature with a more realistic model
                base_value = (base_value * 0.7) + (outdoor_temp * 0.3)  # Weighted average for realism

            # Introduce a more dynamic variation based on time and weather
            variation = random.uniform(-sensor.variation_range, sensor.variation_range)
            if self.env_state.humidity_percent > 70:  # Example condition for high humidity
                variation *= 0.8  # Reduce variation in high humidity
            elif self.env_state.humidity_percent < 30:  # Example condition for low humidity
                variation *= 1.2  # Increase variation in low humidity

            # Combine all factors
            value = base_value + (variation * room_factor * time_factor * weather_impact)

            # Ensure value is within sensor's defined range
            value = max(sensor.min_value, min(sensor.max_value, value))

            # Calculate temperature using Newton's Law of Cooling
            if sensor.type == 'temperature':
                indoor_temp = value  # Current indoor temperature
                U = 0.1  # Overall heat loss coefficient (example value)
                C = 1.0  # Thermal capacitance (example value)
                P_hvac = 0  # HVAC power (can be adjusted based on AC state)
                dt = 1  # Time step in minutes
                dT_dt = -U / C * (indoor_temp - outdoor_temp) + P_hvac / C
                new_temp = indoor_temp + dT_dt * dt
                value = new_temp

            # Calculate humidity using a mass-balance approach
            if sensor.type == 'humidity':
                indoor_humidity = value  # Current indoor humidity
                ventilation_rate = 0.1  # Example ventilation rate
                internal_sources = 0.5  # Example internal moisture sources (e.g., occupants)
                dt = 1  # Time step in minutes
                dH_dt = ventilation_rate * (outdoor_humidity - indoor_humidity) + internal_sources
                new_humidity = indoor_humidity + dH_dt * dt
                value = new_humidity

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
            base_min, base_max = base_ranges.get(sensor_type, base_ranges['temperature'])
            
            # Get current value or use midpoint
            current = sensor.current_value if sensor.current_value is not None else (base_min + base_max) / 2
            
            # Get room type and indoor/outdoor status
            room_type = sensor.device.room.room_type if sensor.device and sensor.device.room else None
            is_indoor = sensor.device.room.is_indoor if sensor.device and sensor.device.room else True
            
            # Handle sensor types
            if sensor_type in ['motion', 'door', 'window', 'smoke', 'co', 'contact_sensor', 'status', 'schedule']:
                return self._handle_binary_sensors(sensor_type, current, base_min, base_max, is_indoor)
            elif sensor_type == 'moisture':
                return self._handle_moisture_sensor(sensor, current, base_min, base_max, is_indoor)
            elif sensor_type == 'mode':
                return self._handle_mode_sensor(sensor, current)
            elif sensor_type == 'set_temperature':
                return self._handle_set_temperature_sensor(sensor, current)
            elif sensor_type == 'power':
                return self._handle_power_sensor(current)
            elif sensor_type == 'fan_speed':
                return self._handle_fan_speed_sensor(current)
            elif sensor_type == 'flow':
                return self._handle_flow_sensor(sensor)
            elif sensor_type == 'color_temp':
                return self._handle_color_temp_sensor()
            elif sensor_type == 'position':
                return self._handle_position_sensor(sensor, current)
            else:
                return self._calculate_sensor_value(sensor_type, base_min, base_max, is_indoor)

        except Exception as e:
            logger.error(f"Error generating sensor value: {str(e)}")
            return sensor.current_value or (base_min + base_max) / 2  # Return current value or midpoint

    def _handle_binary_sensors(self, sensor_type, current, base_min, base_max, is_indoor):
        """Handle binary sensors with stronger weather influence"""
        weather_impact = self._calculate_weather_impact(sensor_type, self.current_weather)
        hour = self.simulation_time.effective_time.hour
        
        # Base probability heavily influenced by weather
        base_prob = 0.2 * weather_impact
        if 8 <= hour <= 22:
            base_prob *= 2.0  # Double probability during active hours
        
        # Specific adjustments for sensor types
        prob = self._calculate_binary_sensor_probability(sensor_type, base_prob, hour, is_indoor)
        
        # Generate value with stronger hysteresis
        if current > 0:
            prob *= 2.0  # Higher probability to stay active if already active
        
        return 1 if random.random() < prob else 0

    def _calculate_binary_sensor_probability(self, sensor_type, base_prob, hour, is_indoor):
        """Calculate probability for binary sensors based on type and conditions"""
        if sensor_type == 'motion':
            return base_prob * (2.0 if 8 <= hour <= 22 else 0.2)  # More pronounced day/night difference
        elif sensor_type in ['smoke', 'co']:
            return 0.001  # Very rare activation
        elif sensor_type == 'contact_sensor':
            return base_prob
        elif sensor_type == 'status':
            return base_prob * 1.5
        elif sensor_type == 'schedule':
            return self._calculate_schedule_probability(hour)
        else:  # door/window
            return self._calculate_door_window_probability(base_prob, is_indoor)

    def _calculate_schedule_probability(self, hour):
        """Calculate probability for schedule sensor"""
        if (5 <= hour <= 8) or (17 <= hour <= 20):
            return 0.7  # High probability during typical watering times
        return 0.05  # Low probability during other times

    def _calculate_door_window_probability(self, base_prob, is_indoor):
        """Calculate probability for door/window sensors"""
        if not is_indoor:
            if self.current_weather in [WeatherCondition.STORMY, WeatherCondition.HEAVY_RAIN, WeatherCondition.HEAVY_SNOW]:
                return base_prob * 0.1  # Very unlikely in severe weather
            elif self.current_weather in [WeatherCondition.SUNNY, WeatherCondition.PARTLY_CLOUDY]:
                return base_prob * 2.0  # Much more likely in nice weather
        return base_prob

    def _handle_moisture_sensor(self, sensor, current, base_min, base_max, is_indoor):
        """Handle moisture sensor for irrigation system"""
        weather_impact = self._calculate_weather_impact('humidity', self.current_weather)
        base_moisture = 40  # Default soil moisture
        
        # Weather effects on soil moisture
        weather_modifier = self._calculate_moisture_weather_effect(weather_impact)
        
        # Calculate time-based drying effect (soil dries out over time)
        hour = self.simulation_time.effective_time.hour
        days_since_update = 0  # Placeholder for actual tracking
        drying_factor = min(30, days_since_update * 3)  # Soil dries out over days
        
        # Apply modifiers
        modified_value = base_moisture + weather_modifier - drying_factor
        
        # Add watering effect if irrigation is active
        if sensor.device:
            for other_sensor in sensor.device.sensors:
                if other_sensor.type == 'flow' and other_sensor.current_value > 0:
                    modified_value += 30  # Significant increase from watering
        
        return max(0, min(100, modified_value))

    def _calculate_moisture_weather_effect(self, weather_impact):
        """Calculate weather effect on moisture"""
        if self.current_weather in [WeatherCondition.RAINY, WeatherCondition.HEAVY_RAIN, WeatherCondition.STORMY]:
            return 20 * weather_impact  # Rain increases soil moisture
        elif self.current_weather in [WeatherCondition.SUNNY, WeatherCondition.PARTLY_CLOUDY]:
            return -15 * (2 - weather_impact)  # Hot/sunny weather decreases soil moisture
        return 0

    def _handle_mode_sensor(self, sensor, current):
        """Handle mode for various devices (HVAC, blinds, etc.)"""
        device_type = sensor.device.type if sensor.device else None
        default_modes = {
            'hvac_system': 0,  # 0=Auto, 1=Cool, 2=Heat, 3=Fan, 4=Dry
            'thermostat': 0,   # 0=Auto, 1=Cool, 2=Heat, 3=Fan
            'blinds': 0,       # 0=Manual, 1=Auto, 2=Scheduled
            'irrigation': 0     # 0=Manual, 1=Scheduled
        }
        default_mode = default_modes.get(device_type, 0)
        return int(current if current is not None else default_mode)

    def _handle_set_temperature_sensor(self, sensor, current):
        """Handle set temperature for HVAC/thermostat"""
        device_type = sensor.device.type if sensor.device else None
        default_temps = {
            'hvac_system': 22.0,  # Central AC default temp
            'thermostat': 21.0,   # Room thermostat default
            'default': 22.0
        }
        default_temp = default_temps.get(device_type, default_temps['default'])
        return current if current is not None else default_temp

    def _handle_power_sensor(self, current):
        """Handle power state for devices"""
        return 1 if current == 1 else 0

    def _handle_fan_speed_sensor(self, current):
        """Handle fan speed for HVAC"""
        return int(current if current is not None else 3)

    def _handle_flow_sensor(self, sensor):
        """Handle water flow rate for irrigation"""
        flow_rate = 0  # Default is no flow
        if sensor.device:
            for other_sensor in sensor.device.sensors:
                if other_sensor.type == 'schedule' and other_sensor.current_value == 1:
                    flow_rate = random.uniform(2.5, 4.5)  # L/min
        return flow_rate

    def _handle_color_temp_sensor(self):
        """Handle color temperature with weather influence"""
        hour = self.simulation_time.effective_time.hour
        weather_impact = self._calculate_weather_impact('light', self.current_weather)
        base_temp = random.uniform(2700, 3500) if hour < 6 or hour > 18 else random.uniform(5000, 6500)
        temp_adjustment = (1 - weather_impact) * 1000  # More pronounced weather effect
        return max(2700, min(6500, base_temp + temp_adjustment))

    def _handle_position_sensor(self, sensor, current):
        """Handle position for smart blinds"""
        position = current  # Start with current position
        mode = self._get_blind_mode(sensor)
        
        if mode == 1:  # Auto (Light-based)
            target_position = self._calculate_blind_target_position()
            position = self._move_towards_target(position, target_position)
        elif mode == 2:  # Scheduled
            target_position = self._calculate_blind_scheduled_position()
            position = self._move_towards_target(position, target_position)
        
        return max(0, min(100, position))

    def _get_blind_mode(self, sensor):
        """Get the mode setting for the blinds"""
        mode = 0  # Default to manual mode
        if sensor.device:
            for other_sensor in sensor.device.sensors:
                if other_sensor.type == 'mode':
                    mode = int(other_sensor.current_value or 0)
        return mode

    def _calculate_blind_target_position(self):
        """Calculate target position for blinds based on light level and weather"""
        weather_impact = self._calculate_weather_impact('light', self.current_weather)
        hour = self.simulation_time.effective_time.hour
        
        if weather_impact > 0.7 and 9 <= hour <= 17:
            return 20  # Mostly closed (20% open)
        elif weather_impact < 0.3 or hour < 7 or hour > 19:
            return 90  # Mostly open
        return 50  # Half open

    def _calculate_blind_scheduled_position(self):
        """Calculate scheduled position for blinds"""
        hour = self.simulation_time.effective_time.hour
        if 7 <= hour <= 9:
            return 80  # Mostly open
        elif 19 <= hour <= 22:
            return 10  # Mostly closed
        elif 22 <= hour or hour < 6:
            return 0  # Fully closed
        return 60  # Partially open

    def _move_towards_target(self, current, target):
        """Move gradually toward target position (max 10% change at a time for realism)"""
        if abs(current - target) > 10:
            return current + (10 if target > current else -10)
        return target

    def _calculate_sensor_value(self, sensor_type, base_min, base_max, is_indoor):
        """Calculate sensor value based on environmental conditions and room type"""
        try:
            # Get current time and weather
            current_time = datetime.now()
            outdoor_temp = self.env_state.temperature_celsius  # Access temperature from EnvironmentalState
            outdoor_humidity = self.env_state.humidity_percent  # Access humidity from EnvironmentalState

            # Calculate base value as the midpoint of the range
            base_value = (base_min + base_max) / 2

            # Calculate temperature using Newton's Law of Cooling
            indoor_temp = base_value  # Current indoor temperature
            U = 0.1  # Overall heat loss coefficient (example value)
            C = 1.0  # Thermal capacitance (example value)
            P_hvac = 0  # HVAC power (can be adjusted based on AC state)
            dt = 1  # Time step in minutes
            dT_dt = -U / C * (indoor_temp - outdoor_temp) + P_hvac / C
            new_temp = indoor_temp + dT_dt * dt
            base_value = new_temp

            # Calculate humidity using a mass-balance approach
            indoor_humidity = base_value  # Current indoor humidity
            ventilation_rate = 0.1  # Example ventilation rate
            internal_sources = 0.5  # Example internal moisture sources (e.g., occupants)
            dH_dt = ventilation_rate * (outdoor_humidity - indoor_humidity) + internal_sources
            new_humidity = indoor_humidity + dH_dt * dt
            base_value = new_humidity

            # Calculate weather impact
            weather_impact = self._calculate_weather_impact(sensor_type, self.env_state.weather_condition)

            # Calculate time-based variation
            hour = current_time.hour
            time_modifier = math.sin((hour - 6) * math.pi / 12) * 0.1 * (base_max - base_min)

            # Apply weather impact modifier
            weather_modifier = (weather_impact - 1.0) * 0.2 * (base_max - base_min)

            # Combine base value with modifiers
            modified_value = base_value + weather_modifier + time_modifier

            # Ensure values stay within the defined range
            modified_value = max(base_min, min(base_max, modified_value))

            # Add small random variation (±5%)
            variation = random.uniform(-0.05, 0.05) * modified_value
            return modified_value + variation
        except Exception as e:
            logger.error(f"Error calculating sensor value for {sensor_type}: {str(e)}")
            return (base_min + base_max) / 2  # Return midpoint as fallback

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
                            
                            logger.info(f"🔍 Processing device: {device.name} at {location} with {len(device.sensors)} sensors")

                            # Update sensor values
                            for sensor in device.sensors:
                                # Merge sensor with current session
                                sensor = session.merge(sensor)
                                
                                # Generate new sensor value
                                new_value = self._generate_sensor_value(sensor)
                                
                                logger.info(f"🔍 Sensor: {sensor.name} - New value: {new_value} - Current value: {sensor.current_value}")

                                # Only update if value has changed significantly
                                if sensor.current_value is None or abs(new_value - sensor.current_value) >= 0.01:
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
                                        logger.debug(f"Published sensor data to topic: {topic} - {sensor_data}")
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
                                logger.debug(f"Device updated: {device.name} - {device.update_counter}")
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
                    
                await asyncio.sleep(self.simulation_interval)  # Update every 2 seconds
                
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
                
                # Update the simulation parameters
                self.update_ac_simulation_parameters(ac_device)
                
                # Log the change
                logger.info(f"Updated whole home AC: Power={'On' if power else 'Off'}, "
                           f"Temp={temperature}°C, Mode={mode}, Fan={fan_speed}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error setting AC parameters: {e}")
            return False

    def update_ac_simulation_parameters(self, ac_device):
        """
        Update the simulation parameters based on the AC device settings.
        """
        if ac_device.is_active:
            # Get the current settings from the AC device
            ac_set_temp = None
            ac_mode = None
            ac_fan_speed = None
            
            for sensor in ac_device.sensors:
                if sensor.type == 'set_temperature':
                    ac_set_temp = sensor.current_value
                elif sensor.type == 'mode':
                    ac_mode = sensor.current_value
                elif sensor.type == 'fan_speed':
                    ac_fan_speed = sensor.current_value
            
            # Logic to adjust the simulation based on the AC settings
            if ac_set_temp is not None:
                # Update the preferred temperature in the simulation
                self.preferred_temperature = ac_set_temp
                logger.info(f"AC set temperature updated to: {ac_set_temp}°C")
            
            # Additional logic can be added here to adjust other simulation parameters
            # based on the AC mode and fan speed if necessary.
        else:
            # Logic for when the AC is off
            logger.info("AC is turned off, maintaining current simulation state.")
    
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
        # Ensure position and mode are integers
        position = int(position)
        mode = int(mode)
        
        # Validate position range
        if position < 0 or position > 100:
            raise ValueError('Position must be between 0 and 100')
        
        # Validate mode range
        if mode < 0 or mode > 2:
            raise ValueError('Mode must be 0 (Manual), 1 (Auto), or 2 (Scheduled)')
        
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

    def add_room(self, room):
        self.rooms.append(room)

    def run_simulation(self, hvac_power, time_step, duration):
        """Run the simulation for a specified duration."""
        for _ in range(int(duration / time_step)):
            # Use existing weather data from env_state
            weather = self.env_state.weather_condition
            outdoor_temp = weather.temperature
            outdoor_humidity = weather.humidity

            # Update the environment based on outdoor conditions
            for room in self.rooms:
                room.update_temperature(outdoor_temp, hvac_power, time_step)
                room.update_humidity(outdoor_humidity, hvac_power * 0.1, time_step)
            # Log or print the current state of each room
            for room in self.rooms:
                print(f"{room.name} - Temp: {room.temperature:.2f}°C, Humidity: {room.humidity:.2f}%")
            time.sleep(time_step)  # Wait for the next time step
