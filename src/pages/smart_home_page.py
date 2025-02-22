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
        self.event_system = EventSystem()
        logger.debug("Created EventSystem instance")
        
        self.simulator = SmartHomeSimulator(self.event_system)
        logger.debug("Created SmartHomeSimulator with EventSystem")
        
        self.floor_plan = FloorPlan(self.event_system)
        logger.debug("Created FloorPlan with EventSystem")
        
        self.active_container = None
        self.scenario_options = []
        self.scenario_select = None
        self.selected_scenario = None
        
        self._setup_event_handlers()
        # Don't load initial data here
        
        # Initialize after all components are ready
        self._initialize_simulation()

    def _load_initial_data(self):
        """Load initial data from database and templates"""
        try:
            with SessionLocal() as session:
                # Load scenarios with their containers
                self.scenarios = session.query(Scenario).options(
                    joinedload(Scenario.containers)
                ).all()
                
                # Find any active scenario and set its container as active
                active_scenario = next((s for s in self.scenarios if s.is_active), None)
                if active_scenario and active_scenario.containers:
                    self.active_container = active_scenario.containers[0]
                    self.selected_scenario = active_scenario
                    logger.info(f"Found active scenario: {active_scenario.name}")
                    logger.info(f"Set active container to: {self.active_container.name}")
                
                # Update UI components
                self.scenario_options = [s.name for s in self.scenarios]
                if self.scenario_select:
                    self.scenario_select.options = self.scenario_options
                    if active_scenario:
                        self.scenario_select.value = active_scenario.name
                    self.scenario_select.update()
                
                logger.debug(f"Loaded {len(self.scenarios)} scenarios")
                
            # Force an update if we have an active container
            if self.active_container:
                asyncio.create_task(self._update_smart_home())
            
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
            with SessionLocal() as session:
                scenario = session.query(Scenario).filter_by(name=scenario_name).first()
                if not scenario:
                    logger.error(f"Scenario not found: {scenario_name}")
                    ui.notify("Scenario not found", type='negative')
                    return
                
                # Stop current scenario if active
                if self.active_container:
                    self.active_container.stop()
                
                # Start all containers in the new scenario
                for container in scenario.containers:
                    if container.start():
                        self.active_container = container
                        logger.info(f"Activated container {container.name} for scenario: {scenario_name}")
                
                ui.notify(f"Scenario activated: {scenario_name}", type='positive')
                asyncio.create_task(self._update_smart_home())
        except Exception as e:
            logger.error(f"Error changing scenario: {str(e)}")
            ui.notify(f"Error changing scenario: {str(e)}", type='negative')

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

    def create_content(self):
        """Create the page content"""
        with ui.column().classes('w-full gap-4'):
            # Scenario selection row
            with ui.card().classes('w-full p-4 bg-white rounded-lg shadow-sm'):
                with ui.row().classes('w-full items-center gap-4'):
                    ui.label('Select Scenario:').classes('text-lg font-bold')
                    self.scenario_select = ui.select(
                        options=self.scenario_options,
                        on_change=lambda e: self._update_scenario_selection(e.value)
                    ).classes('min-w-[300px]')
                    
                    # Add toggle button instead of refresh
                    self.scenario_toggle = ui.button('Start Scenario', 
                                                   on_click=lambda: self._toggle_scenario()).classes('ml-4') \
                                                  .props('icon=play_arrow color=positive')
                    ui.button('Refresh', on_click=self._load_initial_data).classes('ml-2')
            
            # Floor plan visualization
            with ui.card().classes('w-full p-4 bg-white rounded-lg shadow-sm'):
                grid = ui.grid(columns=3).classes("gap-4 room-card-container")
                self.floor_plan.create_floor_plan(container=grid)
                # Update every second and ensure fresh database state
                ui.timer(1.0, self._refresh_and_update)
                logger.debug("Created floor plan with periodic updates")
            
            # Load initial data after creating UI components
            self._load_initial_data()
            return self

    def _update_scenario_selection(self, scenario_name: str):
        """Handle scenario selection without auto-starting"""
        try:
            with SessionLocal() as session:
                # Load the selected scenario with its containers
                scenario = session.query(Scenario).options(
                    joinedload(Scenario.containers)
                ).filter_by(name=scenario_name).first()
                
                if scenario:
                    self.selected_scenario = scenario
                    # If scenario is already active, set the active container
                    if scenario.is_active and scenario.containers:
                        self.active_container = scenario.containers[0]
                        logger.info(f"Set active container to: {self.active_container.name}")
                    
                    self._update_toggle_button_state()
                else:
                    logger.warning(f"Scenario not found: {scenario_name}")
                
        except Exception as e:
            logger.error(f"Error in scenario selection: {str(e)}", exc_info=True)

    def _toggle_scenario(self):
        """Toggle scenario activation"""
        if not self.selected_scenario:
            ui.notify("No scenario selected", type='warning')
            return
        
        try:
            if self.selected_scenario.is_active:
                self._stop_scenario()
            else:
                self._start_scenario()
            
            self._update_toggle_button_state()
        except Exception as e:
            logger.error(f"Scenario toggle failed: {e}")
            ui.notify("Scenario operation failed", type='negative')

    def _update_toggle_button_state(self):
        """Update button appearance based on scenario state"""
        if self.selected_scenario:
            active = self.selected_scenario.is_active
            self.scenario_toggle.props(f'icon={"stop" if active else "play_arrow"}')
            self.scenario_toggle.text = 'Stop Scenario' if active else 'Start Scenario'
            self.scenario_toggle.classes(replace='bg-red' if active else 'bg-positive')
        else:
            self.scenario_toggle.text = 'Select Scenario First'
            self.scenario_toggle.classes(replace='bg-grey')

    def _start_scenario(self):
        """Start the selected scenario"""
        try:
            with SessionLocal() as session:
                # Eager load containers and their devices
                scenario = session.query(Scenario).options(
                    joinedload(Scenario.containers).joinedload(Container.devices)
                ).get(self.selected_scenario.id)
                
                if not scenario:
                    raise ValueError(f"Scenario {self.selected_scenario.id} not found")
                
                # Activate the scenario
                scenario.activate()
                session.commit()  # Commit the activation
                
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
            # Force an immediate update
            asyncio.create_task(self._update_smart_home())
            
        except Exception as e:
            logger.error(f"Error starting scenario: {str(e)}", exc_info=True)
            ui.notify("Failed to start scenario", type='negative')

    def _stop_scenario(self):
        """Stop the selected scenario"""
        try:
            with SessionLocal() as session:
                scenario = session.query(Scenario).get(self.selected_scenario.id)
                scenario.deactivate()
                # Clear the active container
                self.active_container = None
                session.commit()
                
            ui.notify(f"Scenario stopped: {self.selected_scenario.name}", type='warning')
            
        except Exception as e:
            logger.error(f"Error stopping scenario: {str(e)}", exc_info=True)
            ui.notify("Failed to stop scenario", type='negative')

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
        self.simulator.start_simulation()
        logger.info("SmartHomeSimulation started with registered listeners")

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