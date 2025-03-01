from nicegui import ui
from src.utils.smart_home_setup import SmartHomeSetup
from src.components.floor_plan import FloorPlan
from src.utils.event_system import SmartHomeEvent, EventTrigger, EventSystem
from src.models.container import Container
from src.models.device import Device
from src.models.sensor import Sensor
from src.models.scenario import Scenario
from src.models.room import Room
from src.database import get_db as get_db_session, engine, SessionLocal, db_session
from src.constants.device_templates import ROOM_TYPES, SCENARIO_TEMPLATES, DEVICE_TEMPLATES
from sqlalchemy.orm import joinedload
from loguru import logger
import asyncio
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.utils.smart_home_simulator import SmartHomeSimulator
from src.database.database import db_session
from src.utils.initial_data import initialize_scenarios
from collections import defaultdict
from src.models.environmental_factors import WeatherCondition, EnvironmentalState, Location, SimulationTime
from src.services.weather_service import WeatherService, LocationType, LocationQuery
import pytz
from datetime import datetime, time
import time as time_module  # Import time module for update timing
from typing import Optional
import requests
from typing import List, Dict
from dataclasses import dataclass
import math
import random
import weakref
from src.models.option import Option

# Configure logger
logger.add("logs/smart_home.log", rotation="500 MB", level="INFO")

# Sensor mapping dictionary
sensor_room_mapping = {
    # Example mapping of sensor IDs to room names. Update as needed.
    'sensor_1': 'Living Room',
    'sensor_2': 'Kitchen',
    # Add more mappings here
}

@dataclass
class WeatherImpactFactors:
    """Enhanced impact factors with more realistic modifiers"""
    temperature_modifier: float      # Celsius modifier
    humidity_modifier: float        # Percentage points modifier
    light_level_modifier: float    # Percentage points modifier
    air_quality_modifier: float    # AQI points modifier
    noise_level_modifier: float    # Decibel modifier
    wind_chill_modifier: float     # Wind chill effect
    heat_index_modifier: float     # Heat index effect
    pressure_modifier: float       # Pressure modifier
    
    @classmethod
    def get_impact_factors(cls, condition: WeatherCondition, temp: float, humidity: float) -> 'WeatherImpactFactors':
        """Get impact factors considering temperature and humidity"""
        base_factors = {
            WeatherCondition.SUNNY: cls(3.0, -10.0, 30.0, -8.0, 0.0, 0.0, 1.2, -2.0),
            WeatherCondition.PARTLY_CLOUDY: cls(1.0, -5.0, 15.0, -4.0, 0.0, 0.5, 1.0, -1.0),
            WeatherCondition.CLOUDY: cls(-0.5, 5.0, -20.0, 2.0, 0.0, 0.8, 0.9, 0.0),
            WeatherCondition.OVERCAST: cls(-1.5, 10.0, -30.0, 5.0, 0.0, 1.0, 0.8, 1.0),
            WeatherCondition.LIGHT_RAIN: cls(-2.0, 20.0, -40.0, -5.0, 5.0, 1.2, 0.7, 2.0),
            WeatherCondition.RAINY: cls(-3.0, 30.0, -50.0, -10.0, 10.0, 1.5, 0.6, 3.0),
            WeatherCondition.HEAVY_RAIN: cls(-4.0, 40.0, -60.0, -15.0, 15.0, 1.8, 0.5, 4.0),
            WeatherCondition.STORMY: cls(-5.0, 50.0, -70.0, -20.0, 25.0, 2.0, 0.4, 5.0),
            WeatherCondition.LIGHT_SNOW: cls(-6.0, -5.0, -30.0, 5.0, -5.0, 2.2, 0.3, 3.0),
            WeatherCondition.SNOWY: cls(-8.0, -10.0, -40.0, 8.0, -8.0, 2.5, 0.2, 4.0),
            WeatherCondition.HEAVY_SNOW: cls(-10.0, -15.0, -50.0, 10.0, -10.0, 3.0, 0.1, 5.0),
            WeatherCondition.FOGGY: cls(-1.0, 25.0, -45.0, 15.0, -5.0, 1.3, 0.7, 1.0),
            WeatherCondition.WINDY: cls(-2.0, -15.0, -10.0, -12.0, 20.0, 2.0, 0.8, -2.0)
        }
        
        factors = base_factors.get(condition)
        
        # Adjust for extreme temperatures
        if temp > 30:  # Hot weather
            factors.temperature_modifier *= 1.2
            factors.humidity_modifier *= 1.3
        elif temp < 0:  # Cold weather
            factors.temperature_modifier *= 0.8
            factors.humidity_modifier *= 0.7
            
        # Adjust for humidity
        if humidity > 80:  # High humidity
            factors.heat_index_modifier *= 1.3
        elif humidity < 30:  # Low humidity
            factors.heat_index_modifier *= 0.7
            
        return factors

class SmartHomePage:
    """Smart home monitoring and control page"""
    
    def __init__(self, event_system, state_manager=None):
        """Initialize Smart Home Page"""
        logger.info("Initializing SmartHomePage")
        
        # Store components and state
        self.event_system = event_system
        self.state_manager = state_manager
        # Create FloorPlan with our event system instance, not creating a new one
        self.floor_plan = FloorPlan(self.event_system)
        self.scenario_options = []
        self.scenarios = []
        self.selected_scenario = None
        self.active_scenario = None
        
        # Initialize data structures for sensor and device updates
        self.sensors = {}  # Dictionary to store sensor data keyed by sensor_id
        self.devices = {}  # Dictionary to store device data keyed by device_id
        
        # UI components
        self.scenario_select = None
        self.scenario_toggle = None
        self.active_scenario_label = None
        
        # Location components
        self.location_type_select = None
        self.location_input = None
        self.ip_input = None
        self.iata_input = None
        self.metar_input = None
        self.rooms_list = []
        self.weather_result_card = None
        
        # Initialize connections for WebSocket support
        self.connections = weakref.WeakSet()
        
        # Get or create simulator
        self.simulator = SmartHomeSimulator.get_instance(self.event_system)
        logger.debug("Using existing or creating new SmartHomeSimulator")
        
        # Initialize state
        self.scenario_toggle = None
        self.active_scenario = None
        self.scenarios = []
        self.scenario_options = []
        self.selected_scenario = None
        
        # Initialize simulation time
        current_datetime = datetime.now()
        self.simulation_time = SimulationTime(
            start_time=current_datetime,
            custom_time=None
        )
        
        # Location and weather controls
        self.weather_service = WeatherService()
        self.location_type_select = None
        self.location_search = None
        self.location_suggestions = None
        self.latitude_input = None
        self.longitude_input = None
        self.postcode_input = None
        self.iata_input = None
        self.metar_input = None
        self.ip_input = None
        self.timezone_select = None
        self.time_input = None
        self.weather_select = None
        self.weather_result_card = None
        self.current_weather = WeatherCondition.SUNNY
        self.include_aqi = True
        self._current_city = None
        self._current_location_query = None
        
        # Default location
        self.current_location = Location(
            region="San Francisco",
            latitude=37.7749,
            longitude=-122.4194,
            timezone="America/Los_Angeles"
        )
        
        # Popular cities for quick selection
        self.popular_cities = [
            {"name": "San Francisco", "region": "California", "country": "United States", "tz_id": "America/Los_Angeles"},
            {"name": "New York", "region": "New York", "country": "United States", "tz_id": "America/New_York"},
            {"name": "London", "region": "City of London", "country": "United Kingdom", "tz_id": "Europe/London"},
            {"name": "Tokyo", "region": "Tokyo", "country": "Japan", "tz_id": "Asia/Tokyo"},
            {"name": "Singapore", "region": "Singapore", "country": "Singapore", "tz_id": "Asia/Singapore"},
            {"name": "Sydney", "region": "New South Wales", "country": "Australia", "tz_id": "Australia/Sydney"},
            {"name": "Dubai", "region": "Dubai", "country": "United Arab Emirates", "tz_id": "Asia/Dubai"},
            {"name": "Paris", "region": "Ile-de-France", "country": "France", "tz_id": "Europe/Paris"},
            {"name": "Berlin", "region": "Berlin", "country": "Germany", "tz_id": "Europe/Berlin"},
            {"name": "Mumbai", "region": "Maharashtra", "country": "India", "tz_id": "Asia/Kolkata"}
        ]

        self._initialize_simulation()

        # Initialize UI components that haven't been created yet
        # (Don't overwrite floor_plan which was already created)
        self.weather_select = None
        self.weather_card = None
        self.location_select = None
        self.time_slider = None
        self.current_data = {}
        self.device_controls = None
        self.locations = {}
        
        # Register event handlers
        self.setup_event_handlers()
        
        # Initialize weather service if not already done
        if not hasattr(self, 'weather_service') or self.weather_service is None:
            self.weather_service = WeatherService()

        # UI update interval tracking variables
        self.last_ui_update = 0  # Track when we last updated the UI
        self.ui_update_interval = 0.5  # Only update UI every 0.5 seconds max

    def setup_event_handlers(self):
        """Set up event handlers for real-time updates"""
        # Register handlers just for data storage
        self.event_system.on('sensor_update', self.handle_sensor_update)
        self.event_system.on('device_update', self.handle_device_update)
        
        # Start background UI refresh task
        self._start_ui_refresh_task()
        
    def _start_ui_refresh_task(self):
        """Start a task to periodically refresh the UI to ensure it's always up-to-date"""
        async def ui_refresh_loop():
            while True:
                try:
                    # Force a UI refresh every few seconds
                    await asyncio.sleep(2.0)  # Update every 2 seconds
                    await self.update_ui()
                except Exception as e:
                    logger.error(f"Error in UI refresh loop: {e}")
                    await asyncio.sleep(5.0)  # Wait longer if there was an error
        
        # Create the task
        asyncio.create_task(ui_refresh_loop())
        logger.info("Started periodic UI refresh task")

    async def handle_sensor_update(self, data):
        """Store sensor update data without updating UI"""
        try:
            sensor_id = data.get('sensor_id') or data.get('id')
            if not sensor_id:
                logger.warning("Sensor update missing sensor_id")
                return
                
            # Store sensor data for later use
            self.sensors[sensor_id] = {
                'value': data.get('value'),
                'unit': data.get('unit', ''),
                'timestamp': data.get('timestamp', datetime.now().isoformat()),
                'device_id': data.get('device_id'),
                'device_name': data.get('device_name') or data.get('name', ''),
                'location': data.get('location', 'Unknown'),
                'device_type': data.get('device_type') or data.get('type', '')
            }
            logger.debug(f'Stored sensor data: ID={sensor_id}')
        except Exception as e:
            logger.error(f"Error storing sensor update data: {e}")
        
    async def handle_device_update(self, data):
        """Store device update data without updating UI"""
        try:
            # Extract device ID
            device_id = data.get('device_id')
            if not device_id:
                logger.warning("Device update missing device_id")
                return
                
            # Store device data for later use
            self.devices[device_id] = {
                'name': data.get('name', ''),
                'type': data.get('type', ''),
                'location': data.get('location', 'Unknown Location'),
                'update_counter': data.get('update_counter', 0)
            }
            logger.debug(f'Stored device data: ID={device_id}')
        except Exception as e:
            logger.error(f'Error storing device update data: {e}')

    async def update_ui(self):
        """Update the UI with latest sensor and device data"""
        try:
            # Rate limit UI updates to avoid overwhelming the UI
            current_time = time_module.time()
            if (current_time - self.last_ui_update) < self.ui_update_interval:
                # Skip this update as we updated recently
                return
                
            self.last_ui_update = current_time
            
            # Group sensors by location and device type
            locations = {}
            for sensor_id, sensor_data in self.sensors.items():
                location = sensor_data['location']
                device_type = sensor_data['device_type']
                
                if location not in locations:
                    locations[location] = {}
                if device_type not in locations[location]:
                    locations[location][device_type] = []
                    
                locations[location][device_type].append({
                    'sensor_id': sensor_id,
                    'value': sensor_data['value'],
                    'unit': sensor_data['unit'],
                    'device_name': sensor_data['device_name'],
                    'timestamp': sensor_data['timestamp']
                })
            
            # Update the UI components
            for location, device_types in locations.items():
                for device_type, sensors in device_types.items():
                    await self.update_location_section(location, device_type, sensors)
                    
        except Exception as e:
            logger.error(f"Error updating UI: {str(e)}")
            
    async def update_location_section(self, location, device_type, sensors):
        """Update a specific location section in the UI"""
        try:
            # Format sensor data for display
            sensor_displays = []
            for sensor in sensors:
                value_str = f"{sensor['value']:.1f}" if isinstance(sensor['value'], float) else str(sensor['value'])
                sensor_displays.append(f"{sensor['device_name']}: {value_str}{sensor['unit']}")
                
            # Update the UI elements
            section_id = f"{location}-{device_type}"
            await self.event_system.emit('ui_update', {
                'section_id': section_id,
                'location': location.replace('_', ' ').title(),
                'device_type': device_type.replace('_', ' ').title(),
                'sensors': sensor_displays,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error updating location section: {str(e)}")

    def _load_initial_data(self):
        """Load initial data from database and templates"""
        try:
            logger.info("Loading initial data for smart home page")
            
            with SessionLocal() as session:
                # Load all scenarios
                self.scenarios = session.query(Scenario).all()
                self.scenario_options = [s.name for s in self.scenarios]
                
                # Check if there's an active scenario in the database
                active_scenario = session.query(Scenario).filter_by(is_active=True).first()
                
                # Get pre-selected scenario if available (from state manager first, then database)
                if self.state_manager:
                    logger.info("Using state manager to retrieve selected scenario")
                    self.selected_scenario = self.state_manager.get_selected_scenario()
                    if self.selected_scenario:
                        logger.info(f"Retrieved selected scenario from state manager: {self.selected_scenario.name}")
                    
                    # Also get active scenario from state manager
                    self.active_scenario = self.state_manager.get_active_scenario()
                    if self.active_scenario:
                        logger.info(f"Retrieved active scenario from state manager: {self.active_scenario.name}")
                
                # If nothing in state manager, try database
                if not self.selected_scenario:
                    logger.info("No selected scenario in state manager, checking database option")
                    stored_scenario_name = Option.get_value("selected_scenario")
                    if stored_scenario_name:
                        logger.info(f"Found stored scenario name in database: {stored_scenario_name}")
                        # Find the scenario with this name
                        selected_scenario = session.query(Scenario).filter_by(name=stored_scenario_name).first()
                        if selected_scenario:
                            logger.info(f"Setting selected scenario to {selected_scenario.name}")
                            self.selected_scenario = selected_scenario
                            
                            # Update state manager
                            if self.state_manager:
                                self.state_manager.set_selected_scenario(selected_scenario)
                        else:
                            logger.warning(f"Stored scenario name '{stored_scenario_name}' not found in database")
                
                # If still no selected scenario but we have an active one, use that
                if not self.selected_scenario and active_scenario:
                    logger.info(f"Using active scenario as selected: {active_scenario.name}")
                    self.selected_scenario = active_scenario
                    if self.state_manager:
                        self.state_manager.set_selected_scenario(active_scenario)
                
                # If we have an active scenario from database but not from state manager, update state manager
                if active_scenario and not self.active_scenario:
                    logger.info(f"Setting active scenario from database: {active_scenario.name}")
                    self.active_scenario = active_scenario
                    if self.state_manager:
                        # Force refresh the state
                        self.state_manager.notify_scenario_changed(active_scenario.id)
                
                # Load stored location/city from state manager
                if self.state_manager:
                    city = self.state_manager.get_city()
                    location = self.state_manager.get_location()
                    if city:
                        logger.info(f"Retrieved city from state manager: {city}")
                        self._current_city = city
                    if location:
                        logger.info(f"Retrieved location from state manager: {location}")
                        self._current_location = location
                        if 'query' in location:
                            self._current_location_query = location['query']
                
                logger.info("Initial data loaded successfully")
                
                # Schedule an update to UI if we have an active scenario
                if self.active_scenario:
                    logger.info("Scheduling UI update for active scenario")
                    ui.timer(0.5, lambda: self._update_ui_for_active_scenario(), once=True)
                
        except Exception as e:
            logger.error(f"Error loading initial data: {e}", exc_info=True)
            ui.notify("Failed to load initial data", type='negative')

    def _update_ui_for_active_scenario(self):
        """Update UI components to reflect active scenario state"""
        try:
            logger.info("Updating UI for active scenario")
            if not hasattr(self, 'active_scenario') or not self.active_scenario:
                logger.info("No active scenario to update UI for")
                return
            
            # Update scenario selection dropdown
            if hasattr(self, 'scenario_select') and self.scenario_select is not None:
                logger.info(f"Setting scenario dropdown to: {self.active_scenario.name}")
                self.scenario_select.value = self.active_scenario.name
            
            # Update active scenario label
            if hasattr(self, 'active_scenario_label') and self.active_scenario_label is not None:
                logger.info(f"Setting active scenario label to: {self.active_scenario.name}")
                self.active_scenario_label.text = self.active_scenario.name
            
            # Update toggle button state
            if hasattr(self, 'scenario_toggle') and self.scenario_toggle is not None:
                logger.info("Updating scenario toggle button state")
                if self.active_scenario:
                    self.selected_scenario = self.active_scenario
                self._update_toggle_button_state()
        
        except Exception as e:
            logger.error(f"Error updating UI for active scenario: {e}")
            logger.exception("Detailed error trace:")

    async def _update_smart_home(self):
        """Update smart home visualization based on current state"""
        try:
            logger.info("Starting smart home visualization update")
            rooms_data = defaultdict(list)
            
            with db_session() as session:
                containers = session.query(Container).options(
                    joinedload(Container.devices)
                    .joinedload(Device.sensors)
                ).all()
                
                for container in containers:
                    if container.location:
                        # Get actual room type from container's location
                        room = session.query(Room).filter_by(name=container.location).first()
                        if room:
                            room_type = room.room_type.lower()
                            for device in container.devices:
                                device_data = {
                                    'name': device.name,
                                    'type': device.type,
                                    'sensors': [
                                        {
                                            'id': sensor.id,
                                            'name': sensor.name,
                                            'type': sensor.type,
                                            'value': sensor.current_value,  # This will be mapped to 'value' in UI
                                            'unit': sensor.unit,
                                            'room_type': room_type,
                                            'device': device.name,
                                            'location': container.location
                                        }
                                        for sensor in device.sensors
                                    ]
                                }
                                rooms_data[room_type].append(device_data)
            
            logger.debug(f"Room data structure: {rooms_data}")  # Add debug logging
            logger.info(f"Updating {len(rooms_data)} rooms with device data")
            await self.floor_plan.update_sensor_values(rooms_data)
            logger.info("Smart home visualization updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating smart home visualization: {e}")
            logger.exception("Detailed error trace:")
            ui.notify("Error updating smart home visualization", type='negative')

    def _initialize_simulation(self):
        """Start simulation after all handlers are registered"""
        try:
            logger.info("🚀 Starting simulation initialization...")
            
            # Load initial data but don't start any simulation
            logger.info("Loading initial data...")
            self._load_initial_data()
            
            # We've removed the deactivation of active scenarios to preserve their state
            # when returning to this page
            with SessionLocal() as session:
                logger.info("Loading available scenarios...")
                # Load all available scenarios
                scenarios = session.query(Scenario).all()
                self.scenarios = scenarios
                self.scenario_options = [s.name for s in scenarios]
                logger.info(f"Loaded {len(scenarios)} available scenarios: {', '.join(self.scenario_options)}")
                
                # Check for active scenario from state manager first, then database
                if self.state_manager:
                    self.active_scenario = self.state_manager.get_active_scenario()
                    if self.active_scenario:
                        logger.info(f"Retrieved active scenario from state manager: {self.active_scenario.name}")
                
                # If no active scenario from state manager, check database
                if not self.active_scenario:
                    active_scenario = session.query(Scenario).filter_by(is_active=True).first()
                    if active_scenario:
                        logger.info(f"Found active scenario in database: {active_scenario.name}")
                        self.active_scenario = active_scenario
                
                # If we have an active scenario, make sure it's properly set
                if self.active_scenario and not self.selected_scenario:
                    logger.info("Setting selected scenario to active scenario")
                    self.selected_scenario = self.active_scenario
                    # Update state manager
                    if self.state_manager:
                        self.state_manager.set_selected_scenario(self.active_scenario)
                    
            logger.info("✅ Simulation initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Error in simulation initialization: {e}")
            logger.exception("Detailed error trace:")
            ui.notify("Error initializing simulation", type='negative')

    async def _fetch_weather_data(self):
        """Fetch weather data from API"""
        try:
            if not hasattr(self, '_current_location_query'):
                await self._safe_notify('Please select a location first', type='warning')
                return
                
            # Fetch weather data
            weather_data = self.weather_service.get_weather(self._current_location_query, self.include_aqi)
            if weather_data:
                self._update_weather_display(weather_data)
            else:
                await self._safe_notify('No weather data available', type='warning')
            
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
            logger.exception("Full traceback:")
            await self._safe_notify(f'Error fetching weather data: {str(e)}', type='negative')

    async def _update_weather_display(self, weather_data: dict):
        """Update weather display with API data"""
        try:
            # Check if weather_result_card exists and is not None
            if not hasattr(self, 'weather_result_card') or self.weather_result_card is None:
                logger.warning("Cannot update weather display: weather_result_card is None")
                return
                
            # Clear previous content
            self.weather_result_card.clear()
            
            # Update weather display
            with self.weather_result_card:
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label(f"Weather in {weather_data.get('location', {}).get('name', 'Unknown Location')}")
                    ui.label(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
                with ui.row().classes('w-full gap-4 mt-2'):
                    with ui.card().classes('flex-1 p-4'):
                        ui.label('Temperature').classes('text-lg font-bold')
                        temp_c = weather_data.get('temperature')
                        temp_f = (temp_c * 9/5 + 32) if temp_c is not None else None
                        ui.label(f"{temp_c if temp_c is not None else 'N/A'}°C / {temp_f if temp_f is not None else 'N/A'}°F")
                    
                    with ui.card().classes('flex-1 p-4'):
                        ui.label('Condition').classes('text-lg font-bold')
                        ui.label(weather_data.get('description', 'N/A'))
                    
                    with ui.card().classes('flex-1 p-4'):
                        ui.label('Humidity').classes('text-lg font-bold')
                        ui.label(f"{weather_data.get('humidity', 'N/A')}%")
                
                if weather_data.get('air_quality'):
                    with ui.card().classes('w-full p-4 mt-2'):
                        ui.label('Air Quality').classes('text-lg font-bold')
                        with ui.row().classes('w-full gap-4'):
                            with ui.column().classes('flex-1'):
                                ui.label('PM2.5').classes('font-bold')
                                ui.label(f"{weather_data['air_quality'].get('pm2_5', 'N/A')} μg/m³")
                            with ui.column().classes('flex-1'):
                                ui.label('PM10').classes('font-bold')
                                ui.label(f"{weather_data['air_quality'].get('pm10', 'N/A')} μg/m³")
                            with ui.column().classes('flex-1'):
                                ui.label('CO').classes('font-bold')
                                ui.label(f"{weather_data['air_quality'].get('co', 'N/A')} μg/m³")
                            with ui.column().classes('flex-1'):
                                ui.label('NO2').classes('font-bold')
                                ui.label(f"{weather_data['air_quality'].get('no2', 'N/A')} μg/m³")
                            with ui.column().classes('flex-1'):
                                ui.label('O3').classes('font-bold')
                                ui.label(f"{weather_data['air_quality'].get('o3', 'N/A')} μg/m³")
                
                # Update simulator with real weather data
                try:
                    await self._update_simulation_with_weather(weather_data)
                except Exception as e:
                    logger.error(f"Error updating simulation with weather data: {e}")
        
        except Exception as e:
            logger.error(f"Error updating weather display: {e}")
            logger.exception("Full traceback:")
            await self._safe_notify(f'Error updating weather display: {str(e)}', type='negative')

    async def _update_simulation_with_weather(self, weather_data: dict):
        """Update simulation with real weather data"""
        try:
            # Map weather condition to our enum
            condition_text = weather_data.get('description', '').lower()
            weather_mapping = {
                'sunny': WeatherCondition.SUNNY,
                'partly cloudy': WeatherCondition.PARTLY_CLOUDY,
                'cloudy': WeatherCondition.CLOUDY,
                'overcast': WeatherCondition.OVERCAST,
                'light rain': WeatherCondition.LIGHT_RAIN,
                'rain': WeatherCondition.RAINY,
                'heavy rain': WeatherCondition.HEAVY_RAIN,
                'thunderstorm': WeatherCondition.STORMY,
                'light snow': WeatherCondition.LIGHT_SNOW,
                'snow': WeatherCondition.SNOWY,
                'heavy snow': WeatherCondition.HEAVY_SNOW,
                'fog': WeatherCondition.FOGGY,
                'windy': WeatherCondition.WINDY
            }
            
            # Find best matching weather condition
            matched_condition = WeatherCondition.SUNNY  # default
            for key, value in weather_mapping.items():
                if key in condition_text:
                    matched_condition = value
                    break
            
            # Update weather select and trigger simulation update
            # Check if weather_select exists and is not None before using it
            if hasattr(self, 'weather_select') and self.weather_select is not None:
                try:
                    self.weather_select.value = matched_condition.value.replace('_', ' ').title()
                    await self.weather_select.update()
                except Exception as e:
                    logger.error(f"Error updating weather select UI: {e}")
            
            # Update the weather condition regardless of UI component status
            await self._update_weather_condition(matched_condition.value)
            
        except Exception as e:
            logger.error(f"Error updating simulation with weather data: {e}")
            logger.exception("Full traceback:")
            await self._safe_notify(f'Error updating simulation with weather data: {str(e)}', type='negative')

    async def _update_weather_condition(self, condition: str):
        """Update weather condition and simulation state"""
        try:
            if condition:
                self.current_weather = WeatherCondition(condition)
            else:
                logger.warning("Empty weather condition provided, using default SUNNY")
                self.current_weather = WeatherCondition.SUNNY
                
            await self._update_simulation_state()
        except Exception as e:
            logger.error(f"Error updating weather condition: {e}")
            # Use default value in case of error
            self.current_weather = WeatherCondition.SUNNY
            try:
                await self._update_simulation_state()
            except Exception as inner_e:
                logger.error(f"Error in fallback simulation state update: {inner_e}")

    def _update_simulation_time(self, time_str: str):
        """Update simulation time"""
        if time_str:
            try:
                hour, minute = map(int, time_str.split(':'))
                self._update_simulation_state(time(hour, minute))
            except Exception as e:
                logger.error(f"Error updating simulation time: {e}")
        else:
            # Use current time as fallback
            current_time = datetime.now().time()
            self._update_simulation_state(current_time)

    async def _update_simulation_state(self, custom_time: Optional[time] = None):
        """Update simulation state with new environmental conditions"""
        simulation_time = None
        
        try:
            # Create simulation time object safely
            current_datetime = datetime.now()
            simulation_time = SimulationTime(
                start_time=current_datetime,
                custom_time=custom_time
            )
            
            # Check if current_location is valid before proceeding
            if not hasattr(self, 'current_location') or self.current_location is None:
                logger.warning("Cannot update simulation state: current_location is None")
                return
                
            # Get current weather data with error handling
            weather_data = None
            try:
                weather_query = LocationQuery(
                    type=LocationType.LATLON,
                    value=f"{self.current_location.latitude},{self.current_location.longitude}"
                )
                # Calling get_weather without await since it's not an async function
                weather_data = self.weather_service.get_weather(weather_query)
            except Exception as network_error:
                logger.error(f"Error fetching weather data: {network_error}")
                # Continue with None weather_data
            
            # Update simulation state with actual weather data (if available)
            if hasattr(self, 'simulator') and self.simulator is not None:
                if weather_data:
                    self.simulator.update_environmental_state(
                        self.current_weather,
                        self.current_location,
                        simulation_time,
                        weather_data
                    )
                else:
                    # Fallback to default state without weather data
                    self.simulator.update_environmental_state(
                        self.current_weather,
                        self.current_location,
                        simulation_time
                    )
            else:
                logger.warning("Cannot update simulation state: simulator is None")
            
        except Exception as e:
            logger.error(f"Error updating simulation state: {e}")
            logger.exception("Full traceback:")
            
            # Attempt minimal fallback if simulation_time was created
            if simulation_time and hasattr(self, 'simulator') and self.simulator is not None:
                try:
                    # Basic fallback without weather data
                    self.simulator.update_environmental_state(
                        WeatherCondition.SUNNY,  # Use default weather
                        self.current_location,
                        simulation_time
                    )
                except Exception as fallback_error:
                    logger.error(f"Critical error in simulation fallback: {fallback_error}")

    def _update_location_options(self, locations: List[Dict]):
        """Update location select options"""
        try:
            # Keep track of seen locations to avoid duplicates
            seen = set()
            self.location_options = {}  # Map display name to location data
            options = []  # List of display names for select
            
            for loc in locations:
                # Create a unique key for the location
                key = f"{loc['name']}-{loc['region']}-{loc['country']}"
                if key in seen:
                    continue
                seen.add(key)
                
                # Create display name
                display_name = f"{loc['name']}, {loc['region']}"
                
                # Store full location data
                self.location_options[display_name] = {
                    'name': loc['name'],
                    'region': loc['region'],
                    'country': loc['country'],
                    'tz_id': loc.get('tz_id', 'UTC')
                }
                
                # Add display name to options
                options.append(display_name)
            
            # Update select options
            logger.debug(f"Setting location options: {options}")
            self.location_search.options = options
            
        except Exception as e:
            logger.error(f"Error updating location options: {e}")

    async def _update_location_and_weather(self):
        """Update both weather data and environmental state for new location"""
        try:
            # Get current weather data using the city-based query first
            current_weather = self.weather_service.get_weather(self._current_location_query, self.include_aqi)
            
            if not current_weather and self.current_location:
                # Fallback to coordinates if city query fails
                fallback_query = LocationQuery(
                    type=LocationType.CITY,  # Keep using CITY type instead of LATLON
                    value=f"{self.current_location.region}"  # Just use the region name
                )
                current_weather = self.weather_service.get_weather(fallback_query, self.include_aqi)
            
            if current_weather:
                # Extract weather condition from current weather data
                condition_text = current_weather.get('description', '').lower()
                weather_mapping = {
                    'sunny': WeatherCondition.SUNNY,
                    'partly cloudy': WeatherCondition.PARTLY_CLOUDY,
                    'cloudy': WeatherCondition.CLOUDY,
                    'overcast': WeatherCondition.OVERCAST,
                    'light rain': WeatherCondition.LIGHT_RAIN,
                    'rain': WeatherCondition.RAINY,
                    'heavy rain': WeatherCondition.HEAVY_RAIN,
                    'thunderstorm': WeatherCondition.STORMY,
                    'light snow': WeatherCondition.LIGHT_SNOW,
                    'snow': WeatherCondition.SNOWY,
                    'heavy snow': WeatherCondition.HEAVY_SNOW,
                    'fog': WeatherCondition.FOGGY,
                    'windy': WeatherCondition.WINDY
                }
                
                # Find best matching weather condition
                matched_condition = WeatherCondition.SUNNY  # default
                for key, value in weather_mapping.items():
                    if key in condition_text:
                        matched_condition = value
                        break
                
                # Update current weather condition
                self.current_weather = matched_condition
                
                # Prepare weather data with all necessary fields
                weather_state = {
                    'weather_condition': matched_condition.value,
                    'temperature': current_weather.get('temperature', 20.0),
                    'humidity': current_weather.get('humidity', 50.0),
                    'pressure': current_weather.get('pressure', 1013.0),
                    'wind_speed': current_weather.get('wind_speed', 0.0),
                    'description': current_weather.get('description', ''),
                    'air_quality': current_weather.get('air_quality', {})
                }
                
                # Update environmental state with actual weather data
                self.simulator.update_environmental_state(
                    matched_condition,
                    self.current_location,
                    self.simulation_time,
                    weather_state
                )
                logger.info(f"Updated environmental state for {self.current_location.region} with weather: {matched_condition.value}, humidity: {weather_state['humidity']}%")
                
                # Store the values we need to update in the UI
                weather_select_value = matched_condition.value.replace('_', ' ').title()
                weather_display_data = current_weather
                location_region = self.current_location.region
                
                # Update UI elements safely using stored references
                try:
                    if hasattr(self, 'weather_select') and self.weather_select is not None:
                        try:
                            self.weather_select.value = weather_select_value
                            await self.weather_select.update()
                        except Exception as e:
                            logger.error(f"Error updating weather select component: {e}")
                    else:
                        logger.warning("weather_select component not available for update")
                    
                    if hasattr(self, 'weather_result_card') and self.weather_result_card is not None:
                        try:
                            with self.weather_result_card:
                                self.weather_result_card.clear()
                                await self._update_weather_display(weather_display_data)
                        except Exception as e:
                            logger.error(f"Error updating weather result card: {e}")
                    else:
                        logger.warning("weather_result_card component not available for update")
                    
                    # Use a safe notification method that works in background tasks
                    if hasattr(self, 'weather_result_card') and self.weather_result_card is not None:
                        try:
                            with self.weather_result_card:
                                ui.label(f'Updated to {location_region}').classes('text-positive')
                        except Exception as e:
                            logger.error(f"Error adding update notification: {e}")
                except Exception as e:
                    logger.error(f"Error updating UI components: {e}")
                
            else:
                logger.warning("No weather data received for location update")
                # Log warning instead of using UI notification in background task
                logger.warning('Could not fetch weather data for location')
                
        except Exception as e:
            logger.error(f"Error updating location and weather: {e}")
            logger.exception("Full traceback:")
            # Log error instead of using UI notification in background task
            logger.error('Error updating location data')

    def _handle_location_select(self, event):
        """Handle location selection"""
        try:
            logger.debug(f"Location select event: {event}")
            logger.debug(f"Event args: {event.args}")
            logger.debug(f"Available options: {self.location_options.keys()}")
            
            if not event or not event.args:
                logger.debug("No event or args")
                return
                
            # Handle both dictionary and direct string cases
            if isinstance(event.args, dict):
                display_name = event.args.get('label')
            else:
                display_name = event.args[0].get('label') if isinstance(event.args[0], dict) else event.args[0]
                
            if not display_name:
                logger.debug("No display name")
                return
                
            # Try to find a matching location
            matching_name = None
            for name in self.location_options.keys():
                if name.lower() == str(display_name).lower():
                    matching_name = name
                    break
                    
            if not matching_name:
                logger.error(f"No matching location for: {display_name}")
                return
                
            location = self.location_options[matching_name]
            logger.debug(f"Selected location data: {location}")
                
            # Update current location
            self.current_location = Location(
                region=location['name'],
                latitude=40.7128,  # New York coordinates
                longitude=-74.0060,
                timezone=location.get('tz_id', 'UTC')
            )
            logger.debug(f"Updated current location: {self.current_location}")
            
            # Store the selected location in the state manager
            if self.state_manager:
                self.state_manager.set_city(matching_name)
                self.state_manager.set_location(location)
                logger.info(f"Stored city '{matching_name}' and location data in state manager")
            
            # Set current city for display purposes
            self._current_city = matching_name
            
            # Update timezone if available and timezone select exists
            if location.get('tz_id') and hasattr(self, 'timezone_select') and self.timezone_select is not None:
                logger.debug(f"Updating timezone to: {location['tz_id']}")
                self.timezone_select.value = location['tz_id']
            
            # Create location query for weather
            location_query = LocationQuery(
                type=LocationType.CITY,
                value=f"{location['name']}, {location['region']}, {location['country']}"
            )
            
            # Store for weather fetch
            self._current_location_query = location_query
            
            # Fetch weather data and update environmental state
            logger.debug("Fetching weather data and updating environmental state for new location")
            asyncio.create_task(self._update_location_and_weather())
            
        except Exception as e:
            logger.error(f"Error handling location select: {e}")
            logger.exception("Full traceback:")
            logger.error('Error selecting location')

    async def _handle_location_search(self, event):
        """Handle location search input for select filtering"""
        try:
            logger.debug(f"Location search event: {event}")
            # event.args[0] is the filter text
            query = event.args[0] if event.args else ''
            if query and len(query) >= 3:
                locations = self.weather_service.search_locations(query)
                logger.debug(f"Found locations: {locations}")
                
                # Store search results and update options
                self.search_results = locations
                self._update_location_options(self.popular_cities + locations)
            else:
                # If no search query, show only popular cities
                self.search_results = []
                self._update_location_options(self.popular_cities)
                
        except Exception as e:
            logger.error(f"Error in location search: {e}")
            logger.exception("Full traceback:")
            # Show popular cities on error
            self.search_results = []
            self._update_location_options(self.popular_cities)

    def _map_weather_condition(self, condition: str) -> WeatherCondition:
        """Enhanced weather condition mapping with more granular conditions"""
        condition_lower = condition.lower()
        
        condition_mappings = {
            WeatherCondition.SUNNY: [
                'sunny', 'clear', 'fine', 'fair', 'bright'
            ],
            WeatherCondition.PARTLY_CLOUDY: [
                'partly cloudy', 'scattered clouds'
            ],
            WeatherCondition.CLOUDY: [
                'cloudy', 'mostly cloudy'
            ],
            WeatherCondition.OVERCAST: [
                'overcast', 'dull'
            ],
            WeatherCondition.LIGHT_RAIN: [
                'light rain', 'drizzle', 'light shower'
            ],
            WeatherCondition.RAINY: [
                'rain', 'shower', 'precipitation'
            ],
            WeatherCondition.HEAVY_RAIN: [
                'heavy rain', 'downpour', 'torrential'
            ],
            WeatherCondition.STORMY: [
                'thunder', 'storm', 'lightning', 'squall'
            ],
            WeatherCondition.LIGHT_SNOW: [
                'light snow', 'sleet', 'light flurries'
            ],
            WeatherCondition.SNOWY: [
                'snow', 'snowfall'
            ],
            WeatherCondition.HEAVY_SNOW: [
                'heavy snow', 'blizzard'
            ],
            WeatherCondition.FOGGY: [
                'fog', 'mist', 'hazy'
            ],
            WeatherCondition.WINDY: [
                'windy', 'blustery', 'gusty'
            ]
        }

    def _generate_sensor_value(self, sensor: Sensor) -> float:
        """Enhanced sensor value generation with realistic environmental factors"""
        base_ranges = {
            'temperature': {
                'indoor': (18, 25),   # Indoor temperature range
                'outdoor': (-10, 40)  # Outdoor temperature range
            },
            'humidity': {
                'indoor': (30, 60),   # Indoor humidity range
                'outdoor': (20, 100)  # Outdoor humidity range
            },
            'light': {
                'indoor': (0, 500),    # Indoor light level (lux)
                'outdoor': (0, 100000) # Outdoor light level (lux)
            },
            'air_quality': {
                'indoor': (0, 500),    # Indoor AQI
                'outdoor': (0, 500)    # Outdoor AQI
            },
            'pressure': (980, 1020),  # Atmospheric pressure (hPa)
            'noise': {
                'indoor': (30, 70),    # Indoor noise level (dB)
                'outdoor': (40, 100)   # Outdoor noise level (dB)
            },
            'wind_speed': (0, 100),   # Wind speed (km/h)
            'rain_rate': (0, 100),    # Rain rate (mm/h)
            'uv_index': (0, 11)       # UV index
        }
        
        sensor_type = sensor.type.lower()
        location_type = 'indoor' if sensor.room and sensor.room.is_indoor else 'outdoor'
        
        # Get base range for sensor type and location
        if isinstance(base_ranges[sensor_type], dict):
            base_min, base_max = base_ranges[sensor_type][location_type]
        else:
            base_min, base_max = base_ranges[sensor_type]
        
        # Get environmental modifiers
        env_modifier = get_sensor_value_modifier(self.env_state, sensor_type)
        weather_impact = WeatherImpactFactors.get_impact_factors(
            self.current_weather,
            self.env_state.temperature_celsius,
            self.env_state.humidity_percent
        )
        
        # Calculate base value with time-based variation
        hour = self.simulation_time.effective_time.hour
        time_factor = math.sin((hour - 6) * math.pi / 12)  # Daily cycle
        base_value = ((base_max - base_min) / 2) * (1 + time_factor) + base_min
        
        # Apply modifiers
        if sensor_type == 'temperature':
            modified_value = base_value + weather_impact.temperature_modifier
            if location_type == 'indoor':
                modified_value = self._adjust_indoor_temperature(modified_value)
        elif sensor_type == 'humidity':
            modified_value = base_value + weather_impact.humidity_modifier
            if location_type == 'indoor':
                modified_value = self._adjust_indoor_humidity(modified_value)
        elif sensor_type == 'light':
            modified_value = base_value * weather_impact.light_level_modifier
            if location_type == 'indoor':
                modified_value *= 0.1  # Indoor light levels are typically lower
        elif sensor_type == 'air_quality':
            modified_value = base_value + weather_impact.air_quality_modifier
        else:
            modified_value = base_value * env_modifier
        
        # Add small random variation
        variation = random.uniform(-0.05, 0.05) * modified_value
        final_value = modified_value + variation
        
        # Ensure value stays within bounds
        return max(base_min, min(base_max, final_value))

    def _adjust_indoor_temperature(self, outdoor_temp: float) -> float:
        """Adjust indoor temperature based on outdoor temperature"""
        target_temp = 22  # Typical indoor target temperature
        adjustment_factor = 0.2  # How much outdoor temperature affects indoor
        return target_temp + (outdoor_temp - target_temp) * adjustment_factor

    def _adjust_indoor_humidity(self, outdoor_humidity: float) -> float:
        """Adjust indoor humidity based on outdoor humidity"""
        target_humidity = 45  # Typical indoor target humidity
        adjustment_factor = 0.3  # How much outdoor humidity affects indoor
        return target_humidity + (outdoor_humidity - target_humidity) * adjustment_factor

    def _get_time_based_variation(self, sensor_type: str) -> float:
        """Get time-based variation for sensor values"""
        hour = self.simulation_time.effective_time.hour
        
        if sensor_type == 'temperature':
            # Temperature peaks in afternoon (around 14:00)
            return 5 * math.sin((hour - 6) * math.pi / 12)
        elif sensor_type == 'humidity':
            # Humidity highest in early morning
            return -10 * math.sin((hour - 4) * math.pi / 12)
        elif sensor_type == 'light':
            # Light levels follow sun pattern
            if 6 <= hour <= 18:  # Daylight hours
                return 50 * math.sin((hour - 6) * math.pi / 12)
            return 0  # Night time
        
        return 0

    async def _update_scenario_selection(self, scenario_name):
        """Handle scenario selection without auto-starting"""
        try:
            # Handle None, empty string, or non-string input
            logger.info(f"_update_scenario_selection received: {scenario_name} (type: {type(scenario_name)})")
            
            if scenario_name is None or (isinstance(scenario_name, str) and not scenario_name.strip()):
                logger.info("Empty scenario selection - clearing current selection")
                self.selected_scenario = None
                # Clear the stored scenario option
                try:
                    Option.set_value("selected_scenario", "")
                    logger.info("Cleared stored scenario selection in database")
                    
                    # Clear in state manager if available
                    if self.state_manager:
                        self.state_manager.set_selected_scenario(None)
                        logger.info("Cleared selected scenario in state manager")
                except Exception as e:
                    logger.error(f"Error clearing stored scenario selection: {str(e)}", exc_info=True)
                
                try:
                    self._update_toggle_button_state()
                except Exception as e:
                    logger.error(f"Error updating toggle button with null selection: {str(e)}", exc_info=True)
                return
                
            # Convert to string if it's not already
            if not isinstance(scenario_name, str):
                logger.info(f"Converting non-string {type(scenario_name)} to string")
                scenario_name = str(scenario_name)
            
            logger.info(f"Processing scenario selection. Final name: {scenario_name}")
            
            with SessionLocal() as session:
                # Load the selected scenario with its containers
                logger.info(f"Querying database for scenario: {scenario_name}")
                scenario = session.query(Scenario).options(
                    joinedload(Scenario.containers)
                ).filter_by(name=scenario_name).first()
                
                if scenario:
                    logger.info(f"Found scenario in database: {scenario.name} (id: {scenario.id})")
                    self.selected_scenario = scenario
                    logger.info(f"Selected scenario containers: {[c.name for c in scenario.containers]}")
                    
                    # Store the selected scenario in database for persistence
                    try:
                        Option.set_value("selected_scenario", scenario.name)
                        logger.info(f"Stored scenario selection '{scenario.name}' in database")
                        
                        # Update state manager
                        if self.state_manager:
                            self.state_manager.set_selected_scenario(scenario)
                            logger.info(f"Updated selected scenario in state manager: {scenario.name}")
                    except Exception as e:
                        logger.error(f"Error storing scenario selection: {str(e)}", exc_info=True)
                    
                    # Update button state to show 'Start Scenario'
                    try:
                        self._update_toggle_button_state()
                    except Exception as e:
                        logger.error(f"Error updating toggle button: {str(e)}", exc_info=True)
                        # Continue without updating the toggle button
                else:
                    logger.warning(f"Scenario not found in database: {scenario_name}")
                    await self._safe_notify("Scenario not found", notification_type='warning')
            
        except Exception as e:
            logger.error(f"Error in scenario selection: {str(e)}", exc_info=True)
            await self._safe_notify("Error selecting scenario", notification_type='negative')
    
    async def _toggle_scenario(self):
        """Toggle scenario activation"""
        logger.info(f"Toggle scenario called. Selected scenario: {self.selected_scenario.name if self.selected_scenario else 'None'}")
        
        if not self.selected_scenario:
            logger.warning("Attempt to toggle scenario without selection")
            await self._safe_notify("Please select a scenario first", notification_type='warning')
            return
            
        # Refresh the selected scenario status from the database to ensure we have the latest state
        with SessionLocal() as session:
            scenario = session.query(Scenario).get(self.selected_scenario.id)
            if scenario:
                self.selected_scenario = scenario
                logger.info(f"Refreshed scenario from database: {scenario.name} (active: {scenario.is_active})")
            else:
                logger.warning(f"Selected scenario {self.selected_scenario.id} no longer exists in database")
                await self._safe_notify("Selected scenario no longer exists", notification_type='negative')
                self.selected_scenario = None
                return
        
        try:
            logger.info(f"Current scenario {self.selected_scenario.name} - active state: {self.selected_scenario.is_active}")

            if self.selected_scenario.is_active:
                # If scenario is already active, stop it
                self._stop_scenario()
            else:
                # Otherwise start it
                self._start_scenario()
                logger.info(f"Scenario {self.selected_scenario.name} started successfully")
            
            self._update_toggle_button_state()
            
        except Exception as e:
            logger.error(f"Error toggling scenario: {str(e)}", exc_info=True)
            await self._safe_notify(f"Error toggling scenario: {str(e)}", notification_type='negative')

    async def _safe_notify(self, message, notification_type='info'):
        """Safely show notifications that works in any context"""
        try:
            # Create a function that will run in the main event loop
            def show_notification():
                try:
                    # Use notification_type parameter
                    ui.notify(message, type=notification_type)
                except Exception as e:
                    logger.error(f"Error showing notification: {e}")
            
            # Use run_javascript to execute in the proper UI context
            js_code = f"setTimeout(() => {{ui.notify('{message.replace("'", "\\'")}', {{type: '{notification_type}'}});}}, 100);"
            await ui.run_javascript(js_code)
            
        except Exception as e:
            logger.error(f"Failed to display notification: {e}")

    def _update_toggle_button_state(self):
        """Update toggle button state based on selected scenario"""
        try:
            if not hasattr(self, 'scenario_toggle') or self.scenario_toggle is None:
                # Toggle button doesn't exist yet, do nothing
                logger.info("Toggle button doesn't exist yet, skipping update")
                return
                
            if not self.selected_scenario:
                # No scenario selected
                logger.info("No scenario selected, disabling toggle button")
                self.scenario_toggle.text = 'Select Scenario First'
                # Update properties individually to avoid string parsing issues
                self.scenario_toggle.props(remove='color icon disabled')
                self.scenario_toggle.props('color=grey')
                self.scenario_toggle.props('icon=play_arrow')
                self.scenario_toggle.props('disabled=true')
                return
                
            # Check if scenario is active
            is_active = False
            try:
                is_active = bool(self.selected_scenario.is_active)
                logger.info(f"Raw is_active value: {is_active} (type: {type(is_active)})")
            except Exception as e:
                logger.error(f"Error getting is_active status: {e}")
                
            logger.info(f"Updating toggle button for scenario: {self.selected_scenario.name}, active: {is_active}")
            
            if is_active:
                # Scenario is active, button should stop it
                logger.info("Scenario is active, setting Stop button")
                self.scenario_toggle.text = 'Stop Scenario'
                # Update properties individually
                logger.debug("Updating toggle button properties to stop state")
                self.scenario_toggle.props(remove='color icon disabled')
                self.scenario_toggle.props('color=red')
                self.scenario_toggle.props('icon=stop')
                self.scenario_toggle.classes('bg-red-500', remove=False)
                self.scenario_toggle.classes('bg-blue-500', remove=True)
                
                # Update active scenario label
                if hasattr(self, 'active_scenario_label') and self.active_scenario_label is not None:
                    logger.debug(f"Updating active scenario label to: {self.selected_scenario.name}")
                    self.active_scenario_label.text = self.selected_scenario.name
            else:
                # Scenario is not active, button should start it
                logger.info("Scenario is not active, setting Start button")
                self.scenario_toggle.text = 'Start Scenario'
                # Update properties individually
                logger.debug("Updating toggle button properties to start state")
                self.scenario_toggle.props(remove='color icon disabled')
                self.scenario_toggle.props('color=blue')
                self.scenario_toggle.props('icon=play_arrow')
                self.scenario_toggle.classes('bg-blue-500', remove=False)
                self.scenario_toggle.classes('bg-red-500', remove=True)
                # Enable the button since we now have a scenario selected
                self.scenario_toggle.props('disabled=false')
        except Exception as e:
            logger.error(f"Error in _update_toggle_button_state: {str(e)}", exc_info=True)
            # Don't rethrow to prevent UI disruption

    def _start_scenario(self):
        """Start the selected scenario"""
        try:
            with SessionLocal() as session:
                # First, deactivate all currently active scenarios and their containers
                active_scenarios = session.query(Scenario).filter_by(is_active=True).all()
                for active_scenario in active_scenarios:
                    if active_scenario.id != self.selected_scenario.id:
                        logger.info(f"Deactivating previous scenario: {active_scenario.name}")
                        # Deactivate containers
                        for container in active_scenario.containers:
                            container.is_active = False
                            self.floor_plan.update_container_state(container.id, is_active=False)
                        # Deactivate scenario
                        active_scenario.is_active = False
                
                # Eager load containers and their devices for the selected scenario
                scenario = session.query(Scenario).options(
                    joinedload(Scenario.containers).joinedload(Container.devices)
                ).get(self.selected_scenario.id)
                
                if not scenario:
                    raise ValueError(f"Scenario {self.selected_scenario.id} not found")
                
                # Activate only the selected scenario
                scenario.is_active = True
                scenario.activate()
                session.commit()  # Commit the activation
                
                # Refresh scenario state after activation
                session.refresh(scenario)
                self.selected_scenario = scenario
                self.active_scenario = scenario

                # Update active containers in the UI
                for container in scenario.containers:
                    container.is_active = True  # Mark as active in the database
                    logger.info(f"Container activated: {container.name}")
                    # Update the UI for the active container
                    self.floor_plan.update_container_state(container.id, is_active=True)
                
                # Update active scenario label
                if hasattr(self, 'active_scenario_label') and self.active_scenario_label is not None:
                    logger.debug(f"Updating active scenario label to: {scenario.name}")
                    self.active_scenario_label.text = scenario.name

                # Notify the state manager about the scenario change if available
                if self.state_manager:
                    logger.info(f"Notifying state manager about scenario activation: {scenario.id}")
                    self.state_manager.notify_scenario_changed(scenario.id)

                logger.info("Scenario started successfully")
            
        except Exception as e:
            logger.error(f"Error starting scenario: {e}", exc_info=True)
            logger.exception("Detailed error trace:")
            # Don't re-raise the exception to prevent cascading errors

    def _stop_scenario(self):
        """Stop the selected scenario"""
        try:
            logger.info("Attempting to stop the selected scenario.")
            with SessionLocal() as session:
                if self.active_scenario:
                    logger.info(f"Stopping scenario: {self.active_scenario.name} (ID: {self.active_scenario.id})")
                else:
                    logger.info("No active scenario to stop")
                    return

                # First deactivate any currently active scenarios
                active_scenario = session.query(Scenario).filter_by(is_active=True).first()
                if active_scenario:
                    logger.info(f"Stopping scenario: {active_scenario.name} (ID: {active_scenario.id})")
                    
                    # First deactivate all containers
                    for container in active_scenario.containers:
                        try:
                            logger.debug(f"Deactivating container: {container.name} (ID: {container.id})")
                            
                            # Update container status in DB
                            container.is_active = False
                            session.flush()  # Flush changes to get updated state
                            
                            # Update container status in UI
                            logger.info(f"Container {container.name} deactivated")
                            self.floor_plan.update_container_state(container.id, is_active=False)
                        except Exception as container_e:
                            logger.error(f"Error deactivating container {container.name}: {container_e}")
                    
                    # Then deactivate the scenario itself
                    active_scenario.is_active = False
                    active_scenario.deactivate()
                    session.commit()
                    
                    # Update UI
                    if hasattr(self, 'active_scenario_label') and self.active_scenario_label is not None:
                        self.active_scenario_label.text = 'None'
                    
                    # Clear the active scenario reference
                    self.active_scenario = None
                    
                    logger.info(f"Scenario {active_scenario.name} stopped successfully")
                    
                    # Notify the state manager about the scenario change if available
                    if self.state_manager:
                        logger.info(f"Notifying state manager about scenario deactivation")
                        self.state_manager.notify_scenario_changed(None)
                else:
                    logger.warning("No active scenario found to stop")
        
        except Exception as e:
            logger.error(f"Error stopping scenario: {e}", exc_info=True)
            # Don't re-raise to prevent cascading errors

    def _build_scenario_controls(self):
        """Build scenario selection and control section"""
        with ui.card().classes('w-full p-4'):
            # First show active scenario label
            with ui.row().classes('items-center mb-2'):
                ui.label('Active Scenario:').classes('text-lg font-medium')
                self.active_scenario_label = ui.label('None').classes('text-lg font-bold ml-2')
        
            # Then show the controls
            with ui.row().classes('items-center gap-4'):
                # Create scenario select with increased width
                logger.debug(f"Building scenario select with options: {self.scenario_options}")
                
                self.scenario_select = ui.select(
                    label="Select Scenario",
                    options=self.scenario_options,
                    value=self.scenario_options[0],
                ).props('outlined options-dense')
                self.scenario_select.classes('min-w-[300px] md:min-w-[400px]')
                
                # Try to load the previously selected scenario from the database
                try:
                    stored_scenario_name = Option.get_value("selected_scenario", "")
                    
                    if stored_scenario_name and stored_scenario_name.strip():
                        # If a scenario was previously selected, set the dropdown value and update state
                        logger.info(f"Setting scenario select to previously stored value: {stored_scenario_name}")
                        self.scenario_select.value = stored_scenario_name
                        
                        # Update the selected scenario object
                        with SessionLocal() as session:
                            scenario = session.query(Scenario).options(
                                joinedload(Scenario.containers)
                            ).filter_by(name=stored_scenario_name).first()
                            
                            if scenario:
                                logger.info(f"Loaded previously selected scenario: {scenario.name}")
                                self.selected_scenario = scenario
                                # Update button state after a short delay to ensure UI is ready
                                ui.timer(0.5, lambda: self._update_toggle_button_state(), once=True)
                            else:
                                logger.warning(f"Stored scenario name '{stored_scenario_name}' not found in database")
                except Exception as e:
                    logger.error(f"Error loading previous scenario selection: {str(e)}", exc_info=True)
                
                # Use a simplified direct callback that gets the value
                # This works better with NiceGUI's event handling
                async def on_select_change(e):
                    try:
                        # For NiceGUI select components, the value is in event.value 
                        # or event.args when using update:model-value event
                        if hasattr(e, 'value'):
                            value = e.value
                        elif hasattr(e, 'args'):
                            value = e.args
                        else:
                            value = str(e)
                            
                        logger.info(f"Direct scenario select value: {value} (type: {type(value)})")
                        
                        # For select components, sometimes the value comes as the entire selection object
                        if isinstance(value, dict) and 'label' in value:
                            value = value['label']
                            
                        await self._update_scenario_selection(value)
                    except Exception as ex:
                        logger.error(f"Error in direct scenario selection: {str(ex)}", exc_info=True)
            
                # Use model-value event which is more reliable for select components
                self.scenario_select.on('update:model-value', on_select_change)
                logger.debug("Scenario select component built")
                
                # Create toggle button
                self.scenario_toggle = ui.button(
                    'Start Scenario',
                    on_click=self._handle_toggle_click
                ).classes('bg-blue-500 text-white')
    
    def _handle_toggle_click(self):
        """Handle toggle button click in a safe way that preserves context"""
        try:
            # Create a task but don't wait for it
            asyncio.create_task(self._toggle_scenario())
        except Exception as e:
            logger.error(f"Error handling toggle button click: {str(e)}")

    def _build_location_controls(self):
        """Build location and environmental controls section"""
        with ui.card().classes('w-full p-4'):
            ui.label('Location & Weather Controls').classes('text-h6 mb-4')
            
            with ui.column().classes('w-full gap-4'):
                self._build_location_type_selection()
                self._build_location_inputs()
                self._build_weather_result_card()

    def _build_location_type_selection(self):
        """Build location type selection dropdown"""
        location_type_options = [t.value.title() for t in LocationType]
        with ui.row().classes('items-start gap-4 flex-wrap'):
            with ui.column().classes('flex-1'):
                self.location_type_select = ui.select(
                    label='Location Type',
                    options=location_type_options,
                    value=location_type_options[0],
                ).props('outlined dense').classes('w-64')
                self.location_type_select.on('update:model-value', 
                                               lambda e: self._handle_location_type_change(e))

    def _build_location_inputs(self):
        """Build inputs for various location types"""
        with ui.row().classes('items-start gap-4 flex-wrap'):
            self._build_city_search_input()
            self._build_lat_lon_inputs()
            self._build_postcode_input()
            self._build_iata_input()
            self._build_metar_input()
            self._build_ip_input()

    def _build_city_search_input(self):
        """Build city search input"""
        with ui.column().classes('flex-1').bind_visibility_from(
            self.location_type_select, 'value',
            lambda v: v and v.lower() == LocationType.CITY.value.lower()):
            self.location_search = ui.select(
                label='Search City',
                options=[],
                with_input=True,
            ).props('outlined dense').classes('w-96')
            self.search_results = []
            self._update_location_options(self.popular_cities)
            
            # Set the last selected city if available from state manager
            if self.state_manager:
                saved_city = self.state_manager.get_city()
                if saved_city and saved_city in self.location_options:
                    logger.info(f"Setting previously selected city from state manager: {saved_city}")
                    self.location_search.value = saved_city
                    
                    # If we have a saved location data, fetch weather data
                    location_data = self.state_manager.get_location()
                    if location_data:
                        logger.info("Previously saved location data found, restoring location and fetching weather")
                        self.current_location = Location(
                            region=location_data.get('name', 'Unknown'),
                            latitude=40.7128,  # Default coordinates 
                            longitude=-74.0060,
                            timezone=location_data.get('tz_id', 'UTC')
                        )
                        
                        # Create location query for weather
                        self._current_location_query = LocationQuery(
                            type=LocationType.CITY,
                            value=f"{location_data.get('name', '')}, {location_data.get('region', '')}, {location_data.get('country', '')}"
                        )
                        
                        # Fetch weather for the saved location
                        asyncio.create_task(self._update_location_and_weather())
            
            self.location_search.on('filter', self._handle_location_search)
            self.location_search.on('update:model-value', self._handle_location_select)

    def _build_lat_lon_inputs(self):
        """Build latitude and longitude inputs"""
        with ui.column().classes('flex-1').bind_visibility_from(
            self.location_type_select, 'value',
            lambda v: v and v.lower() == LocationType.LATLON.value.lower()):
            with ui.row().classes('gap-4'):
                self.latitude_input = ui.number(
                    label='Latitude',
                    min=-90,
                    max=90,
                    step=0.000001,
                    format='%.6f'
                ).props('outlined dense').classes('w-48')
                self.longitude_input = ui.number(
                    label='Longitude',
                    min=-180,
                    max=180,
                    step=0.000001,
                    format='%.6f'
                ).props('outlined dense').classes('w-48')

    def _build_postcode_input(self):
        """Build postcode input"""
        with ui.column().classes('flex-1').bind_visibility_from(
            self.location_type_select, 'value',
            lambda v: v and v.lower() == LocationType.POSTCODE.value.lower()):
            self.postcode_input = ui.input(
                label='Postal Code'
            ).props('outlined dense').classes('w-48')

    def _build_iata_input(self):
        """Build IATA code input"""
        with ui.column().classes('flex-1').bind_visibility_from(
            self.location_type_select, 'value',
            lambda v: v and v.lower() == LocationType.IATA.value.lower()):
            self.iata_input = ui.input(
                label='IATA Code'
            ).props('outlined dense').classes('w-48')

    def _build_metar_input(self):
        """Build METAR code input"""
        with ui.column().classes('flex-1').bind_visibility_from(
            self.location_type_select, 'value',
            lambda v: v and v.lower() == LocationType.METAR.value.lower()):
            self.metar_input = ui.input(
                label='METAR Code'
            ).props('outlined dense').classes('w-48')

    def _build_ip_input(self):
        """Build IP address input"""
        with ui.column().classes('flex-1').bind_visibility_from(
            self.location_type_select, 'value',
            lambda v: v and v.lower() == LocationType.IP.value.lower()):
            self.ip_input = ui.input(
                label='IP Address (leave empty for auto)'
            ).props('outlined dense').classes('w-64')

    def _build_weather_result_card(self):
        """Build weather result card"""
        self.weather_result_card = ui.card().classes('w-full p-4 mt-4')
        with self.weather_result_card:
            ui.label('Weather Data').classes('text-h6 mb-2')

    def _build_floor_plan(self):
        """Build floor plan visualization section"""
        with ui.card().classes('w-full p-4'):
            ui.label('Smart Home Floor Plan').classes('text-h6 mb-4')
            # Create the floor plan with normalized room types
            self.floor_plan.create_floor_plan()

    def build(self):
        """Build the smart home page UI"""
        with ui.column().classes('w-full max-w-6xl mx-auto p-4 gap-4'):
            # Load data before building UI
            self._load_initial_data()
            
            # Build UI components
            self._build_scenario_controls()
            self._build_location_controls()
            self._build_floor_plan()


    # Asynchronously update the floor plan view with the new sensor reading using the location provided in the sensor data.
    async def update_floorplan(sensor_data):
        """Asynchronously update the floor plan view with the new sensor reading using the location provided in the sensor data."""
        sensor_id = sensor_data.get('id')
        reading = sensor_data.get('value')
        room = sensor_data.get('location')
        if room:
            # Normalize room type before updating
            normalized_room = room.lower().replace(' ', '_')
            # Update the UI element corresponding to the room
            print(f"FloorPlan Update - Room: {normalized_room}, Sensor: {sensor_id}, Reading: {reading}")
        else:
            print(f"Sensor update missing location info: {sensor_data}")
        await asyncio.sleep(0)  # Dummy await to ensure this is a coroutine
