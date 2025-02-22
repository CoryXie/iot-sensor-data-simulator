from nicegui import ui
from src.utils.smart_home_setup import SmartHomeSetup
from src.components.floor_plan import FloorPlan
from src.utils.event_system import SmartHomeEvent, EventTrigger, EventSystem
from src.models.container import Container
from src.models.device import Device
from src.models.sensor import Sensor
from src.models.scenario import Scenario
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

# Configure logger
logger.add("logs/smart_home.log", rotation="500 MB", level="INFO")

class SmartHomePage:
    """Smart home monitoring and control page"""
    
    def __init__(self):
        """Initialize Smart Home Page"""
        logger.info("Initializing SmartHomePage")
        self.event_system = EventSystem()
        self.simulator = SmartHomeSimulator(self.event_system)
        self.floor_plan = FloorPlan(self.event_system)
        self.active_container = None
        self.scenario_options = []
        self.scenario_select = None  # Initialize as None
        
        self._setup_event_handlers()
        # Don't load initial data here

    def _load_initial_data(self):
        """Load initial data from database and templates"""
        try:
            with SessionLocal() as session:
                # Load scenarios with their containers
                self.scenarios = session.query(Scenario).options(
                    joinedload(Scenario.containers)
                ).all()
                
                # Update scenario activation logic
                for scenario in self.scenarios:
                    if scenario.is_active:
                        for container in scenario.containers:
                            container.start()
                
                # Refresh scenario list with proper query
                scenarios = session.query(Scenario).options(
                    joinedload(Scenario.containers)
                ).all()
                
                # Update UI components
                self.scenario_options = [s.name for s in scenarios]
                if self.scenario_select:
                    self.scenario_select.options = self.scenario_options
                    self.scenario_select.update()
                
                logger.debug(f"Loaded {len(scenarios)} scenarios")
                
        except Exception as e:
            logger.error(f"Data loading failed: {str(e)}")
            ui.notify("Failed to load scenarios", type='negative')

    def _setup_event_handlers(self):
        """Set up event handlers for real-time updates"""
        @self.event_system.on('device_update')
        async def handle_device_update(event_name, device_data):
            self._update_room_data(device_data['location'], [device_data])

    def _update_smart_home(self):
        """Update smart home visualization"""
        if not self.active_container:
            return
            
        try:
            with SessionLocal() as session:
                container = session.query(Container).options(
                    joinedload(Container.devices)
                    .joinedload(Device.sensors)
                ).get(self.active_container.id)
                
                if container:
                    room_devices = {}
                    for device in container.devices:
                        room_type = device.location
                        if room_type not in room_devices:
                            room_devices[room_type] = []
                        
                        device_data = {
                            'id': device.id,
                            'name': device.name,
                            'type': device.type,
                            'sensors': [{
                                'id': sensor.id,
                                'name': sensor.name,
                                'type': sensor.type,
                                'value': sensor.current_value,
                                'unit': sensor.unit
                            } for sensor in device.sensors]
                        }
                        room_devices[room_type].append(device_data)
                    
                    # Update all rooms with their devices
                    for room_type, devices in room_devices.items():
                        self.floor_plan.update_room_data(
                            room_type.lower().replace(' ', '_'),
                            devices
                        )
        except Exception as e:
            logger.error(f"Error updating smart home: {str(e)}")

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
                self._update_smart_home()
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
            
            self.floor_plan.update_room_data(
                room_type.lower().replace(' ', '_'),
                formatted_devices
            )
        except Exception as e:
            logger.error(f"Error updating room data: {str(e)}")

    def create_content(self):
        """Create the page content"""
        # Scenario selection row
        with ui.row().classes('w-full items-center gap-4 mb-4'):
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
        with ui.card().classes('w-full h-[calc(100vh-200px)] p-4 bg-white rounded-lg shadow-sm'):
            self.floor_plan.create_floor_plan()
            ui.timer(1.0, lambda: self._update_smart_home())
        
        # Load initial data after creating UI components
        self._load_initial_data()
        return self

    def _update_scenario_selection(self, scenario_name: str):
        """Handle scenario selection without auto-starting"""
        self.selected_scenario = next((s for s in self.scenarios if s.name == scenario_name), None)
        self._update_toggle_button_state()

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
        with SessionLocal() as session:
            # Eager load containers and their devices
            scenario = session.query(Scenario).options(
                joinedload(Scenario.containers).joinedload(Container.devices)
            ).get(self.selected_scenario.id)
            
            scenario.activate()
            session.commit()
        ui.notify(f"Scenario started: {self.selected_scenario.name}", type='positive')

    def _stop_scenario(self):
        """Stop the selected scenario"""
        with SessionLocal() as session:
            scenario = session.query(Scenario).get(self.selected_scenario.id)
            scenario.deactivate()
            session.commit()
        ui.notify(f"Scenario stopped: {self.selected_scenario.name}", type='warning')