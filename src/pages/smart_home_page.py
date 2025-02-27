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
from typing import Optional
import requests
from typing import List, Dict
from dataclasses import dataclass
import math
import random

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
    
    def __init__(self, event_system):
        """Initialize Smart Home Page"""
        logger.info("Initializing SmartHomePage")
        
        self.event_system = event_system
        
        self.devices = {}
        self.sensors = {}
        self.setup_event_handlers()
        
        # Get or create simulator
        self.simulator = SmartHomeSimulator.get_instance(self.event_system)
        logger.debug("Using existing or creating new SmartHomeSimulator")
        
        # Create floor plan
        self.floor_plan = FloorPlan(self.event_system)
        logger.debug("Created FloorPlan with EventSystem")
        
        # Initialize state
        self.active_container = None
        self.scenario_options = []
        self.scenario_select = None
        self.selected_scenario = None
        self.scenarios = []
        self.scenario_toggle = None
        
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

    def setup_event_handlers(self):
        """Set up event handlers for real-time updates"""
        self.event_system.on('sensor_update', self.handle_sensor_update)
        self.event_system.on('device_update', self.handle_device_update)
        
    async def handle_sensor_update(self, data):
        """Handle real-time sensor updates"""
        sensor_id = data['sensor_id']
        self.sensors[sensor_id] = {
            'value': data['value'],
            'unit': data['unit'],
            'timestamp': data['timestamp'],
            'device_id': data['device_id'],
            'device_name': data['device_name'],
            'location': data['location'],
            'device_type': data['device_type']
        }
        await self.update_ui()
        
    async def handle_device_update(self, data):
        """Handle real-time device updates"""
        logger.debug(f'Handling device update with data: {data}')  # Log the incoming data
        try:
            # Check for the 'location' key and handle its absence
            location = data.get('location', 'Unknown Location')  # Default value if location is missing
            device_id = data['device_id']
            self.devices[device_id] = {
                'name': data['name'],
                'type': data['type'],
                'location': location,
                'update_counter': data['update_counter']
            }
            await self.update_ui()
        except Exception as e:
            logger.error(f'Error handling device update: {e}')
            ui.notify("Failed to load scenarios", type='negative')
        
    async def update_ui(self):
        """Update the UI with latest sensor and device data"""
        try:
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
            with SessionLocal() as session:
                # Load scenarios with their containers
                self.scenarios = session.query(Scenario).options(
                    joinedload(Scenario.containers)
                ).all()
                
                # Update scenario options
                self.scenario_options = [s.name for s in self.scenarios]
                
                # Don't auto-select or activate any scenario
                self.selected_scenario = None
                self.active_container = None
                
                # Update UI components if they exist
                if self.scenario_select:
                    self.scenario_select.options = self.scenario_options
                    self.scenario_select.value = None  # No default selection
                    self.scenario_select.update()
                
                # Update button state if it exists
                self._update_toggle_button_state()
                
                logger.debug(f"Loaded {len(self.scenarios)} scenarios")
                
        except Exception as e:
            logger.error(f"Data loading failed: {str(e)}", exc_info=True)
            ui.notify("Failed to load scenarios", type='negative')

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

    def _change_scenario(self, scenario_name: str):
        """Handle scenario selection change"""
        try:
            # First stop any currently active scenario
            if self.selected_scenario and self.selected_scenario.is_active:
                self._stop_scenario()
            
            with SessionLocal() as session:
                # Load the selected scenario with its containers
                scenario = session.query(Scenario).options(
                    joinedload(Scenario.containers)
                ).filter_by(name=scenario_name).first()
                
                if scenario:
                    self.selected_scenario = scenario
                    # Reset active container since we're selecting a new scenario
                    self.active_container = None
                    logger.info(f"Selected new scenario: {scenario_name}")
                    
                    # Update button state to show 'Start Scenario'
                    self._update_toggle_button_state()
                else:
                    logger.warning(f"Scenario not found: {scenario_name}")
                    ui.notify("Scenario not found", type='warning')
                
        except Exception as e:
            logger.error(f"Error in scenario selection: {str(e)}", exc_info=True)
            ui.notify("Error selecting scenario", type='negative')

    def _update_room_data(self, room_type: str, devices: list):
        """Update room visualization with latest device data"""
        try:
            formatted_devices = []
            for device in devices:
                device_info = {
                    'name': device['name'],
                    'type': device['type'],
                    'sensors': [{
                        'name': s['name'],
                        'value': s['value'],
                        'unit': s['unit']
                    } for s in device['sensors']]
                }
                formatted_devices.append(device_info)
            
            logger.debug(f"Updating room {room_type} with {len(formatted_devices)} devices")

            # Normalize room type to match floor plan's format
            normalized_room_type = room_type.lower().replace(' ', '_')
            self.floor_plan.update_room_data(normalized_room_type, formatted_devices)
        except Exception as e:
            logger.error(f"Error updating room data: {str(e)}")

    def build(self):
        """Build the smart home page UI"""
        with ui.column().classes('w-full max-w-6xl mx-auto p-4 gap-4'):
            self._build_scenario_controls()
            self._build_location_controls()
            self._build_floor_plan()

    def _build_scenario_controls(self):
        """Build scenario selection and control section"""
        with ui.card().classes('w-full p-4'):
            with ui.row().classes('items-center gap-4'):
                # Create scenario select with increased width
                logger.debug(f"Building scenario select with options: {self.scenario_options}")
                
                self.scenario_select = ui.select(
                    options=self.scenario_options,
                    label="Select Scenario"
                ).props('outlined options-dense')
                self.scenario_select.classes('min-w-[300px] md:min-w-[400px]')
                self.scenario_select.on('update:model-value', self._handle_scenario_select_change)
                logger.debug("Scenario select component built")
                
                # Create toggle button
                self.scenario_toggle = ui.button(
                    'Start Scenario',
                    on_click=self._toggle_scenario
                ).classes('bg-blue-500 text-white')

    def _build_location_controls(self):
        """Build location and environmental controls section"""
        with ui.card().classes('w-full p-4'):
            with ui.column().classes('w-full gap-4'):
                # Location Type Selection
                with ui.row().classes('items-start gap-4 flex-wrap'):
                    # Create options list for location type select
                    location_type_options = [t.value.title() for t in LocationType]
                    
                    with ui.column().classes('flex-1'):
                        self.location_type_select = ui.select(
                            label='Location Type',
                            options=location_type_options,
                            value=location_type_options[0],
                        ).props('outlined dense').classes('w-64')  # Wider select
                        self.location_type_select.on('update:model-value', 
                                                   lambda e: self._handle_location_type_change(e))
                
                # Location Inputs Container
                with ui.row().classes('items-start gap-4 flex-wrap'):
                    # City search
                    with ui.column().classes('flex-1').bind_visibility_from(
                        self.location_type_select, 'value',
                        lambda v: v.lower() == LocationType.CITY.value):
                        
                        # Create initial options from popular cities
                        self.location_search = ui.select(
                            label='Search City',
                            options=[],
                            with_input=True,
                        ).props('outlined dense').classes('w-96')  # Wider select
                        
                        # Initialize search results and set initial options
                        self.search_results = []
                        self._update_location_options(self.popular_cities)
                        
                        self.location_search.on('filter', self._handle_location_search)
                        self.location_search.on('update:model-value', self._handle_location_select)

                    # Lat/Lon inputs
                    with ui.column().classes('flex-1').bind_visibility_from(
                        self.location_type_select, 'value',
                        lambda v: v.lower() == LocationType.LATLON.value):
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
                    
                    # Postcode input
                    with ui.column().classes('flex-1').bind_visibility_from(
                        self.location_type_select, 'value',
                        lambda v: v.lower() == LocationType.POSTCODE.value):
                        
                        self.postcode_input = ui.input(
                            label='Postal Code'
                        ).props('outlined dense').classes('w-48')
                    
                    # IATA input
                    with ui.column().classes('flex-1').bind_visibility_from(
                        self.location_type_select, 'value',
                        lambda v: v.lower() == LocationType.IATA.value):
                        
                        self.iata_input = ui.input(
                            label='IATA Code'
                        ).props('outlined dense').classes('w-48')
                    
                    # METAR input
                    with ui.column().classes('flex-1').bind_visibility_from(
                        self.location_type_select, 'value',
                        lambda v: v.lower() == LocationType.METAR.value):
                        
                        self.metar_input = ui.input(
                            label='METAR Code'
                        ).props('outlined dense').classes('w-48')
                    
                    # IP input
                    with ui.column().classes('flex-1').bind_visibility_from(
                        self.location_type_select, 'value',
                        lambda v: v.lower() == LocationType.IP.value):
                        
                        self.ip_input = ui.input(
                            label='IP Address (leave empty for auto)'
                        ).props('outlined dense').classes('w-64')
                    
                    # Weather result card
                    self.weather_result_card = ui.card().classes('w-full p-4 mt-4')
                
                # Remove the Time and Weather Controls section
                # Keep related variables for compatibility with other code
                self.time_input = None  
                self.weather_select = None
                # Set defaults for the variables that would have been set by these controls
                self.current_weather = WeatherCondition.SUNNY
                self.include_aqi = True

    def _build_floor_plan(self):
        """Build floor plan visualization section"""
        with ui.card().classes('w-full p-4'):
            ui.label('Smart Home Floor Plan').classes('text-h6 mb-4')
            # Create the floor plan with normalized room types
            self.floor_plan.create_floor_plan()

    def _show_location_input(self, input_type: str):
        """Show the selected location input and hide others"""
        input_cards = {
            'city': self.city_card,
            'latlon': self.latlon_card,
        }
        
        for card_type, card in input_cards.items():
            if card_type == input_type:
                card.remove_class('hidden')
            else:
                card.add_class('hidden')

    def _handle_location_type_change(self, location_type: str):
        """Handle location type change with validation"""
        try:
            # Convert back to enum value for internal use
            location_type = location_type.upper()
            self._show_location_input(location_type)
            
        except Exception as e:
            logger.error(f"Error handling location type change: {e}")
            ui.notify("Error changing location type", type='negative')

    def _handle_scenario_select_change(self, event):
        """Handle raw selection change event from UI"""
        try:
            logger.debug(f"Received selection event: {event}")
            
            # Extract scenario name from event
            if hasattr(event, 'args') and isinstance(event.args, dict):
                scenario_name = event.args.get('label')
            else:
                scenario_name = event
                
            logger.debug(f"Extracted scenario name: {scenario_name}")
            self._update_scenario_selection(scenario_name)
            
        except Exception as e:
            logger.error(f"Error handling scenario selection event: {e}", exc_info=True)
            ui.notify("Error selecting scenario", type='negative')

    def _update_scenario_selection(self, scenario_name: str):
        """Handle scenario selection without auto-starting"""
        try:
            if not scenario_name:  # Handle empty selection
                logger.info("Empty scenario selection - clearing current selection")
                self.selected_scenario = None
                self._update_toggle_button_state()
                return

            logger.debug(f"Processing scenario selection. Name: {scenario_name}")
            
            with SessionLocal() as session:
                # Load the selected scenario with its containers
                logger.debug(f"Querying database for scenario: {scenario_name}")
                scenario = session.query(Scenario).options(
                    joinedload(Scenario.containers)
                ).filter_by(name=scenario_name).first()
                
                if scenario:
                    logger.info(f"Found scenario in database: {scenario.name} (id: {scenario.id})")
                    self.selected_scenario = scenario
                    # Don't set active container until scenario is started
                    self.active_container = None
                    logger.debug(f"Selected scenario containers: {[c.name for c in scenario.containers]}")
                    
                    # Update button state to show 'Start Scenario'
                    self._update_toggle_button_state()
                else:
                    logger.warning(f"Scenario not found in database: {scenario_name}")
                    ui.notify("Scenario not found", type='warning')
                
        except Exception as e:
            logger.error(f"Error in scenario selection: {e}", exc_info=True)
            ui.notify("Error selecting scenario", type='negative')

    def _toggle_scenario(self):
        """Toggle scenario activation"""
        logger.debug(f"Toggle scenario called. Selected scenario: {self.selected_scenario.name if self.selected_scenario else 'None'}")
        
        if not self.selected_scenario:
            logger.warning("Attempt to toggle scenario without selection")
            ui.notify("Please select a scenario first", type='warning')
            return
        
        try:
            logger.debug(f"Current scenario state - Active: {self.selected_scenario.is_active}")
            if self.selected_scenario.is_active:
                self._stop_scenario()
            else:
                self._start_scenario()
            
            self._update_toggle_button_state()
        except Exception as e:
            logger.error(f"Scenario toggle failed: {e}", exc_info=True)
            ui.notify("Scenario operation failed", type='negative')

    def _update_toggle_button_state(self):
        """Update button appearance based on scenario state"""
        if not hasattr(self, 'scenario_toggle') or not self.scenario_toggle:
            return  # Skip if button hasn't been created yet
            
        if self.selected_scenario:
            active = self.selected_scenario.is_active
            self.scenario_toggle.props(remove='disabled')  # Enable the button
            if active:
                self.scenario_toggle.props('icon=stop color=red')
                self.scenario_toggle.text = 'Stop Scenario'
            else:
                self.scenario_toggle.props('icon=play_arrow color=green')
                self.scenario_toggle.text = 'Start Scenario'
        else:
            self.scenario_toggle.text = 'Select Scenario First'
            self.scenario_toggle.props('disabled color=grey icon=play_arrow')
            self.scenario_toggle.props('disabled')

    def _start_scenario(self):
        """Start the selected scenario"""
        try:
            with SessionLocal() as session:
                # First deactivate any currently active scenarios
                session.query(Scenario).update({'is_active': False})
                session.commit()
                
                # Eager load containers and their devices
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
                
                # Set the first container as active
                if scenario.containers:
                    # Get a fresh container instance
                    container_id = scenario.containers[0].id
                    self.active_container = session.query(Container).get(container_id)
                    logger.info(f"Set active container to: {self.active_container.name}")
                else:
                    logger.warning("Scenario has no containers")
                    self.active_container = None
                
            ui.notify(f"Scenario started: {self.selected_scenario.name}", type='positive')
            # Update button state to show Stop
            self._update_toggle_button_state()
            # Force an immediate update
            asyncio.create_task(self._update_smart_home())
            
        except Exception as e:
            logger.error(f"Error starting scenario: {str(e)}", exc_info=True)
            ui.notify("Failed to start scenario", type='negative')

    def _stop_scenario(self):
        """Stop the selected scenario"""
        try:
            with SessionLocal() as session:
                if self.selected_scenario:
                    # Get fresh scenario instance
                    scenario = session.query(Scenario).get(self.selected_scenario.id)
                    if scenario:
                        scenario.is_active = False
                        session.commit()
                        session.refresh(scenario)
                        self.selected_scenario = scenario
                
                # Clear the active container
                self.active_container = None
                
                # Stop the simulator
                self.simulator.stop_simulation()
                
            ui.notify("Scenario stopped", type='warning')
            logger.info("Scenario stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping scenario: {e}")
            ui.notify("Error stopping scenario", type='negative')

    def _refresh_and_update(self):
        """Refresh container from database and update UI"""
        if self.active_container:
            try:
                with SessionLocal() as session:
                    # Refresh container reference
                    container = session.query(Container).get(self.active_container.id)
                    if container:
                        self.active_container = container
                        asyncio.create_task(self._update_smart_home())
                    else:
                        logger.warning("Active container no longer exists in database")
                        self.active_container = None
            except Exception as e:
                logger.error(f"Error refreshing container: {str(e)}", exc_info=True)

    def _initialize_simulation(self):
        """Start simulation after all handlers are registered"""
        try:
            logger.info("🚀 Starting simulation initialization...")
            
            # Load initial data but don't start any simulation
            logger.info("Loading initial data...")
            self._load_initial_data()
            
            # Initialize scenarios without activating any
            with SessionLocal() as session:
                logger.info("Checking for active scenarios...")
                # Deactivate any active scenarios
                active_count = session.query(Scenario).filter_by(is_active=True).count()
                if active_count > 0:
                    logger.info(f"Deactivating {active_count} active scenarios")
                    session.query(Scenario).update({'is_active': False})
                    session.commit()
                
                # Load scenarios for selection without activating
                scenarios = session.query(Scenario).all()
                self.scenarios = scenarios
                self.scenario_options = [s.name for s in scenarios]
                logger.info(f"Loaded {len(scenarios)} available scenarios: {', '.join(self.scenario_options)}")
                
                self.selected_scenario = None  # Ensure no scenario is selected
                self.active_container = None   # Ensure no container is active
                
            logger.info("✅ Simulation initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Error in simulation initialization: {e}")
            logger.exception("Detailed error trace:")
            ui.notify("Error initializing simulation", type='negative')

    async def _fetch_weather_data(self):
        """Fetch weather data from API"""
        try:
            if not hasattr(self, '_current_location_query'):
                ui.notify('Please select a location first', type='warning')
                return
                
            # Fetch weather data
            weather_data = self.weather_service.get_weather(self._current_location_query, self.include_aqi)
            if weather_data:
                self._update_weather_display(weather_data)
            else:
                ui.notify('No weather data available', type='warning')
            
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
            logger.exception("Full traceback:")
            ui.notify(f'Error fetching weather data: {str(e)}', type='negative')

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

    def _reset_weather_settings(self):
        """Reset weather settings to default values"""
        self.location_type_select.value = LocationType.CITY.value
        self.location_search.value = ''
        self.current_location = Location(
            region="San Francisco",
            latitude=37.7749,
            longitude=-122.4194,
            timezone="America/Los_Angeles"
        )
        self.timezone_select.value = self.current_location.timezone
        self.time_input.value = datetime.now().strftime('%H:%M')
        self.weather_select.value = WeatherCondition.SUNNY.value
        self.include_aqi = True
        self._update_simulation_state()
        ui.notify('Weather settings reset to default values')

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
                weather_data = await self.weather_service.get_current_weather(
                    LocationQuery(
                        type=LocationType.LATLON,
                        value=f"{self.current_location.latitude},{self.current_location.longitude}"
                    )
                )
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
            
    async def _handle_location_select(self, event):
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
            ui.notify('Error selecting location', type='negative')

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

    def _handle_location_search(self, event):
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