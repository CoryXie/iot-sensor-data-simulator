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
        with SessionLocal() as session:
            try:
                # Initialize scenarios with the current session
                initialize_scenarios(session)
                
                # Refresh scenario list with proper query
                scenarios = session.query(Scenario).options(
                    joinedload(Scenario.container)
                ).all()
                
                # Update UI components
                self.scenario_options = [s.name for s in scenarios]
                self.scenario_select.options = self.scenario_options
                self.scenario_select.update()
                
                # Log results
                logger.debug(f"Loaded {len(scenarios)} scenarios")
                for s in scenarios:
                    logger.trace(f"Scenario: {s.name} (Container: {s.container.id if s.container else 'None'})")
                    
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
                
                # Start new scenario
                container = session.query(Container).get(scenario.container_id)
                if container.start():
                    self.active_container = container
                    logger.info(f"Activated scenario: {scenario_name}")
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
            # Create the select component here in the proper context
            self.scenario_select = ui.select(
                options=self.scenario_options,
                on_change=lambda e: self._change_scenario(e.value)
            ).classes('min-w-[300px]')
            ui.button('Refresh', on_click=self._load_initial_data).classes('ml-4')
        
        # Floor plan visualization
        with ui.card().classes('w-full h-[calc(100vh-200px)] p-4 bg-white rounded-lg shadow-sm'):
            self.floor_plan.create_floor_plan()
            ui.timer(1.0, lambda: self._update_smart_home())
        
        # Load initial data after creating UI components
        self._load_initial_data()
        return self