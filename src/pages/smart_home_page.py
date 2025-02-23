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
from src.components.device_controls import DeviceControls
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

# Configure logger
logger.add("logs/smart_home.log", rotation="500 MB", level="INFO")

# Sensor mapping dictionary
sensor_room_mapping = {
    # Example mapping of sensor IDs to room names. Update as needed.
    'sensor_1': 'Living Room',
    'sensor_2': 'Kitchen',
    # Add more mappings here
}

class SmartHomePage:
    """Smart home monitoring and control page"""
    
    def __init__(self):
        """Initialize Smart Home Page"""
        logger.info("Initializing SmartHomePage")
        
        # Get or create event system
        self.event_system = EventSystem.get_instance()
        logger.debug("Using existing or creating new EventSystem instance")
        
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
            country="United States",
            region="San Francisco",
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
        
        # Setup handlers and initialize
        self._setup_event_handlers()
        self._initialize_simulation()

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

    def _setup_event_handlers(self):
        """Set up event handlers for real-time updates"""
        try:
            # Define handlers first
            async def handle_device_update(data):
                """Handle device update events"""
                try:
                    device_id = data.get('device_id')
                    if device_id:
                        with SessionLocal() as session:
                            device = session.query(Device).filter_by(id=device_id).first()
                            if device:
                                logger.debug(f"Device {device.name} updated, counter: {device.update_counter}")
                except Exception as e:
                    logger.error(f"Error handling device update: {e}")

            async def handle_sensor_update(data):
                """Handle sensor update events"""
                try:
                    device_id = data.get('device_id')
                    sensor_id = data.get('sensor_id')
                    if device_id and sensor_id:
                        with SessionLocal() as session:
                            device = session.query(Device).filter_by(id=device_id).first()
                            if device:
                                logger.debug(f"Sensor update for device {device.name}, counter: {device.update_counter}")
                except Exception as e:
                    logger.error(f"Error handling sensor update: {e}")

            # Register handlers
            self.event_system.on('device_update', handle_device_update)
            self.event_system.on('sensor_update', handle_sensor_update)
            logger.info("Event handlers registered successfully")

        except Exception as e:
            logger.error(f"Error setting up event handlers: {e}")

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

            self.floor_plan.update_room_data(
                room_type.lower().replace(' ', '_'),
                formatted_devices
            )
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
                            options=location_type_options,
                            value=location_type_options[0],
                            label="Location Type"
                        ).props('outlined options-dense').classes('w-full')
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
                        ).props('outlined dense').classes('w-full')
                        
                        # Initialize search results and set initial options
                        self.search_results = []
                        self._update_location_options(self.popular_cities)
                        
                        self.location_search.on('filter', self._handle_location_search)
                        self.location_search.on('update:model-value', self._handle_location_select)

                    # Lat/Lon inputs
                    with ui.column().classes('flex-1').bind_visibility_from(
                        self.location_type_select, 'value',
                        lambda v: v.lower() == LocationType.LATLON.value):
                        self.latitude_input = ui.number(
                            label='Latitude',
                            placeholder='-90 to 90'
                        ).props('outlined dense').classes('w-full')
                        self.longitude_input = ui.number(
                            label='Longitude',
                            placeholder='-180 to 180'
                        ).props('outlined dense').classes('w-full')
                    
                    # Other location type inputs...
                    
                    # Fetch Weather Button
                    ui.button('Fetch Weather Data', 
                             on_click=self._fetch_weather_data).classes('bg-blue-500 text-white')
                
                # Weather Result Display
                self.weather_result_card = ui.card().classes('w-full p-4 mt-4')
                
                # Time and Weather Controls
                with ui.row().classes('items-center gap-4 mt-4'):
                    self.time_input = ui.input(
                        label='Simulation Time',
                        value=datetime.now().strftime('%H:%M')
                    ).props('outlined dense type=time').classes('w-full')
                    self.time_input.on('update:model-value', self._update_simulation_time)
                    
                    # Create weather options as a list of strings
                    weather_options = [w.value.replace('_', ' ').title() 
                                     for w in WeatherCondition]
                    self.weather_select = ui.select(
                        options=weather_options,
                        value=self.current_weather.value.replace('_', ' ').title(),
                        label='Weather Condition'
                    ).props('outlined dense').classes('w-full')
                    self.weather_select.on('update:model-value', 
                        lambda v: self._update_weather_condition(v.lower().replace(' ', '_')))
                    
                    ui.switch('Include Air Quality', value=True).bind_value(
                        self, 'include_aqi'
                    ).classes('mt-4')

    def _build_floor_plan(self):
        """Build floor plan visualization section"""
        with ui.card().classes('w-full p-4'):
            ui.label('Smart Home Floor Plan').classes('text-h6 mb-4')
            # Only create the floor plan, initialization is done in constructor
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
            # Load initial data but don't start any simulation
            self._load_initial_data()
            
            # Initialize scenarios without activating any
            with SessionLocal() as session:
                # Deactivate any active scenarios
                session.query(Scenario).update({'is_active': False})
                session.commit()
                
                # Load scenarios for selection without activating
                scenarios = session.query(Scenario).all()
                self.scenarios = scenarios
                self.scenario_options = [s.name for s in scenarios]
                self.selected_scenario = None  # Ensure no scenario is selected
                self.active_container = None   # Ensure no container is active
                
            logger.info("Simulation initialized without auto-start")
            
        except Exception as e:
            logger.error(f"Error in simulation initialization: {e}")
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

    def _update_weather_display(self, weather_data: dict):
        """Update weather display with API data"""
        try:
            # Clear previous content
            if self.weather_result_card:
                self.weather_result_card.clear()
            
            # Update weather display
            with self.weather_result_card:
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label(f"Weather in {weather_data.get('location', {}).get('name', 'Unknown Location')}")
                    ui.label(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
                with ui.row().classes('w-full gap-4 mt-2'):
                    with ui.card().classes('flex-1 p-4'):
                        ui.label('Temperature').classes('text-lg font-bold')
                        ui.label(f"{weather_data.get('temp_c', 'N/A')}°C / {weather_data.get('temp_f', 'N/A')}°F")
                    
                    with ui.card().classes('flex-1 p-4'):
                        ui.label('Condition').classes('text-lg font-bold')
                        ui.label(weather_data.get('condition', {}).get('text', 'N/A'))
                    
                    with ui.card().classes('flex-1 p-4'):
                        ui.label('Humidity').classes('text-lg font-bold')
                        ui.label(f"{weather_data.get('humidity', 'N/A')}%")
                
                if weather_data.get('air_quality'):
                    with ui.card().classes('w-full p-4 mt-2'):
                        ui.label('Air Quality').classes('text-lg font-bold')
                        aqi = weather_data['air_quality'].get('us-epa-index', 'N/A')
                        ui.label(f"US EPA Index: {aqi}")
                
                # Update simulator with real weather data
                self._update_simulation_with_weather(weather_data)
        
        except Exception as e:
            logger.error(f"Error updating weather display: {e}")
            ui.notify('Error updating weather display', type='negative')

    def _update_simulation_with_weather(self, weather_data: dict):
        """Update simulation with real weather data"""
        try:
            # Map weather condition to our enum
            condition_text = weather_data.get('condition', {}).get('text', '').lower()
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
            self.weather_select.value = matched_condition.value
            self._update_weather_condition(matched_condition.value)
            
        except Exception as e:
            logger.error(f"Error updating simulation with weather data: {e}")

    def _reset_weather_settings(self):
        """Reset weather settings to default values"""
        self.location_type_select.value = LocationType.CITY.value
        self.location_search.value = ''
        self.current_location = Location(
            country="United States",
            region="San Francisco",
            timezone="America/Los_Angeles"
        )
        self.timezone_select.value = self.current_location.timezone
        self.time_input.value = datetime.now().strftime('%H:%M')
        self.weather_select.value = WeatherCondition.SUNNY.value
        self.include_aqi = True
        self._update_simulation_state()
        ui.notify('Weather settings reset to default values')

    def _update_weather_condition(self, condition: str):
        """Update weather condition and simulation state"""
        self.current_weather = WeatherCondition(condition)
        self._update_simulation_state()

    def _update_simulation_time(self, time_str: str):
        """Update simulation time"""
        hour, minute = map(int, time_str.split(':'))
        self._update_simulation_state(time(hour, minute))

    def _update_simulation_state(self, custom_time: Optional[time] = None):
        """Update simulation state with new environmental conditions"""
        simulation_time = SimulationTime(
            datetime=datetime.now(),
            custom_time=custom_time
        )
        
        self.simulator.update_environmental_state(
            self.current_weather,
            self.current_location,
            simulation_time
        )

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
                country=location['country'],
                region=location['name'],
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
            
            # Fetch weather data for the new location
            logger.debug("Fetching weather data for new location")
            asyncio.create_task(self._fetch_weather_data())
            
        except Exception as e:
            logger.error(f"Error handling location select: {e}")
            logger.exception("Full traceback:")
            ui.notify('Error selecting location', type='negative')

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

async def update_floorplan(sensor_data):
    """Asynchronously update the floor plan view with the new sensor reading using the location provided in the sensor data."""
    sensor_id = sensor_data.get('id')
    reading = sensor_data.get('value')
    room = sensor_data.get('location')
    if room:
        # Update the UI element corresponding to the room
        print(f"FloorPlan Update - Room: {room}, Sensor: {sensor_id}, Reading: {reading}")
    else:
        print(f"Sensor update missing location info: {sensor_data}")
    await asyncio.sleep(0)  # Dummy await to ensure this is a coroutine