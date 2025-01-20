from nicegui import ui
from utils.smart_home_simulator import SmartHomeSimulator
from utils.smart_home_setup import SmartHomeSetup
from utils.floor_plan import FloorPlan
from utils.scenario_panel import ScenarioPanel
from utils.event_system import EventSystem, SmartHomeEvent, EventTrigger
from models.container import Container
from models.device import Device
from models.sensor import Sensor
from utils.simulator import Simulator
from constants.device_templates import DEVICE_TEMPLATES, ROOM_TYPES, SCENARIO_TEMPLATES
from constants.sensor_errors import SENSOR_ERRORS_UI_MAP_EN, ERROR_MESSAGES
from loguru import logger
import asyncio
import json

# Configure logger
logger.add("logs/smart_home.log", rotation="500 MB", level="INFO")

class SmartHomePage:
    """Smart home monitoring and control page"""
    
    def __init__(self):
        logger.info("Initializing SmartHomePage")
        self.floor_plan = FloorPlan()
        self.event_system = EventSystem()
        self.simulator = SmartHomeSimulator()
        self.smart_home_setup = SmartHomeSetup()
        self.scenario_panel = ScenarioPanel(on_scenario_change=self._handle_scenario_change)
        self._setup_default_events()
        self.alert_container = None
        self.active_scenario_id = None
        self.sensor_simulators = {}  # Store simulators by sensor ID
        self.update_timer = None  # Store reference to timer
        self.main_container = None  # Store reference to main container

    def create_page(self):
        """Create the smart home page"""
        # Cancel existing timer if any
        if self.update_timer:
            self.update_timer.active = False
            
        with ui.column().classes('w-full gap-4') as self.main_container:
            # Header with current status
            with ui.card().classes('w-full p-4'):
                ui.label('Smart Home Control').classes('text-2xl font-bold')
                
            # Main content in two columns
            with ui.row().classes('w-full gap-4'):
                # Left column: Floor Plan and Alerts
                with ui.column().classes('w-2/3 gap-4'):
                    # Floor Plan
                    with ui.card().classes('w-full'):
                        ui.label('Floor Plan').classes('text-xl font-bold mb-4')
                        self.floor_plan.create_floor_plan()
                    
                    # Alerts Panel
                    with ui.card().classes('w-full'):
                        ui.label('Alerts').classes('text-xl font-bold mb-4')
                        self.alert_container = ui.column().classes('w-full')
                
                # Right column: Scenario Control and Setups
                with ui.column().classes('w-1/3 gap-4'):
                    # Scenarios Section
                    with ui.card().classes('w-full p-4'):
                        ui.label('Scenarios').classes('text-xl font-bold mb-4')
                        self.setups_container = ui.column().classes('w-full')
                        self._update_setups_list()
                    
                    # Active Scenario Details
                    with ui.card().classes('w-full p-4'):
                        ui.label('Scenario Schedule').classes('text-xl font-bold mb-4')
                        self.scenario_panel.create_panel()

            # Initialize active scenarios first
            self._restore_active_scenario()

            # Create single timer for updates
            self.update_timer = ui.timer(5.0, self._update_smart_home)
            self.update_timer.active = True

        # Force initial update of setups list
        self._update_setups_list()

    def _restore_active_scenario(self):
        """Restore previously active scenario after app restart"""
        try:
            # Find active container
            active_container = Container.query.filter_by(is_active=True)\
                .filter(Container.name.like('Smart Home - %'))\
                .first()
            
            if active_container:
                logger.info(f"Found active scenario: {active_container.name}")
                scenario_name = active_container.name.replace('Smart Home - ', '')
                
                # Set active scenario ID
                self.active_scenario_id = active_container.id
                
                # Start the container
                active_container.start(None)
                
                # Clear any existing floor plan data to force re-initialization
                for room_type in ROOM_TYPES:
                    if room_type in self.floor_plan.rooms:
                        room = self.floor_plan.rooms[room_type]
                        room['ui_initialized'] = False
                        if room['device_container']:
                            room['device_container'].clear()
                
                # Clear existing simulators and reinitialize
                self.sensor_simulators.clear()
                
                # Initialize simulators for all sensors
                for device in active_container.devices:
                    for sensor in device.sensors:
                        try:
                            simulator = Simulator(sensor=sensor)
                            self.sensor_simulators[sensor.id] = simulator
                            logger.info(f"Created simulator for sensor: {sensor.name} (ID: {sensor.id})")
                        except Exception as e:
                            logger.error(f"Error initializing simulator for sensor {sensor.name}: {str(e)}")
                
                # Update scenario panel
                self.scenario_panel._update_scenario(scenario_name)
                
                # Force a complete UI refresh
                self._update_setups_list()
                
                # Force an immediate update of the floor plan with binding initialization
                self._update_smart_home()
                
                logger.info(f"Successfully restored scenario: {scenario_name}")
                ui.notify(f'Restored {scenario_name} scenario', type='positive')
                
                # Ensure update timer is running
                if not self.update_timer or not self.update_timer.active:
                    self.update_timer = ui.timer(5.0, self._update_smart_home)
                    self.update_timer.active = True
                    logger.info("Started update timer")
                
                # Force a second update after a short delay to ensure bindings are active
                async def delayed_update():
                    await asyncio.sleep(1)
                    self._update_smart_home()
                
                asyncio.create_task(delayed_update())
                
            else:
                logger.info("No active scenario found to restore")
                
        except Exception as e:
            logger.exception(f"Error restoring active scenario: {str(e)}")
            ui.notify(f'Error restoring active scenario: {str(e)}', type='warning')

    def _activate_scenario(self, scenario_name: str):
        """Activate a specific scenario"""
        try:
            logger.info(f"Activating scenario: {scenario_name}")
            # First, stop any active scenario
            if self.active_scenario_id is not None:
                self._stop_scenario(self.active_scenario_id)
            
            # Create and start the new scenario
            container = self.smart_home_setup.create_scenario(scenario_name)
            if not container:
                logger.error(f"Failed to create scenario: {scenario_name}")
                ui.notify(f'Failed to create scenario: {scenario_name}', type='negative')
                return
            
            self.active_scenario_id = container.id
            self._start_scenario(container.id)
            
            # Update the scenario panel
            self.scenario_panel._update_scenario(scenario_name)
            
            logger.info(f"Successfully activated scenario: {scenario_name}")
            ui.notify(f'Activated {scenario_name} scenario', type='positive')
        except Exception as e:
            logger.exception(f"Error activating scenario: {str(e)}")
            ui.notify(f'Error activating scenario: {str(e)}', type='negative')

    def _update_smart_home(self):
        """Update the smart home display"""
        if not self.main_container or not self.main_container.client:
            logger.debug("Main container not available, skipping update")
            return True
            
        logger.debug("Updating smart home display")
        try:
            # Process any scheduled scenarios
            self.scenario_panel.process_scheduled_scenarios()
            
            # Update floor plan if there's an active scenario
            if self.active_scenario_id:
                container = Container.get_by_id(self.active_scenario_id)
                if container:
                    logger.info(f"Updating floor plan for container: {container.name}")
                    # Group devices by room
                    room_devices = {}
                    for device in container.devices:
                        # Extract room name from device name
                        room_name = None
                        for room_type in ROOM_TYPES:
                            if device.name.startswith(room_type):
                                room_name = room_type
                                break
                        
                        if room_name and room_name in self.floor_plan.rooms:
                            if room_name not in room_devices:
                                room_devices[room_name] = []
                            
                            # Format device data
                            device_data = {
                                'name': device.name.split(' - ')[1],  # Get device type
                                'sensors': []
                            }
                            
                            # Add sensor data with real-time values
                            for sensor in device.sensors:
                                try:
                                    simulator = self.sensor_simulators.get(sensor.id)
                                    if simulator:
                                        generated_data = simulator.generate_data()
                                        current_value = generated_data.get('value', sensor.base_value)
                                        logger.debug(f"Generated value for {sensor.name}: {current_value}")
                                    else:
                                        current_value = sensor.base_value
                                        logger.warning(f"No simulator for {sensor.name}, using base: {current_value}")
                                    
                                    unit = self._get_unit_display(sensor.unit)
                                    sensor_data = {
                                        'name': sensor.name,
                                        'base_value': sensor.base_value,
                                        'current_value': current_value,
                                        'unit': unit
                                    }
                                    device_data['sensors'].append(sensor_data)
                                    
                                    # Process events based on new value
                                    self.event_system.process_sensor_update(sensor.unit, current_value, room_name)
                                    
                                except Exception as e:
                                    logger.error(f"Error processing sensor {sensor.name}: {str(e)}")
                                    continue
                            
                            room_devices[room_name].append(device_data)
                    
                    # Update each room in the floor plan
                    for room_name, devices in room_devices.items():
                        self.floor_plan.update_room_data(room_name, devices)
                
                return True
            return True
        except Exception as e:
            logger.exception(f"Error updating smart home: {str(e)}")
            return True

    def _get_unit_display(self, unit_code: int) -> str:
        """Get the display string for a unit code"""
        unit_map = {
            0: '°C',  # Temperature
            1: '%',   # Humidity
            2: 'lux', # Light level
            3: 'ppm', # Air quality
            4: '%',   # Brightness
            5: '',    # Status (0-1)
            6: 'dB',  # Sound level
            7: 'ppm', # CO2
            8: '%',   # Motion
        }
        # Return empty string if unit_code is None
        if unit_code is None:
            return ''
        return unit_map.get(unit_code, '')

    def _setup_default_events(self):
        """Setup default smart home events"""
        # Motion triggers lights event
        motion_light = SmartHomeEvent(
            name="Motion Light Control",
            description="Turn on lights when motion is detected",
            triggers=[
                EventTrigger(22, lambda x: x == 1, 14)  # Motion sensor triggers brightness
            ],
            actions=[
                lambda: self._handle_motion_trigger()
            ]
        )
        self.event_system.add_event(motion_light)
        
        # Temperature comfort event
        temp_comfort = SmartHomeEvent(
            name="Temperature Comfort",
            description="Monitor temperature comfort levels",
            triggers=[
                EventTrigger(0, lambda x: x < 18 or x > 26)  # Temperature outside comfort zone
            ],
            actions=[
                lambda: self._handle_temperature_alert()
            ]
        )
        self.event_system.add_event(temp_comfort)

    async def _handle_scenario_change(self, scenario_name: str):
        """Handle scenario changes"""
        try:
            logger.info(f"Handling scenario change to: {scenario_name}")
            # First clean up any existing scenario
            if self.active_scenario_id:
                # Clear old scenario
                old_container = Container.get_by_id(self.active_scenario_id)
                if old_container:
                    logger.debug(f"Stopping old scenario: {old_container.name}")
                    old_container.stop()  # Stop the old container
                    
                self.simulator.set_scenario(None)
                self.active_scenario_id = None
                self.sensor_simulators.clear()  # Clear all sensor simulators
                
                # Clear all room displays
                for room_type in ROOM_TYPES:
                    if room_type in self.floor_plan.rooms:
                        device_container = self.floor_plan.rooms[room_type]['device_container']
                        if device_container and device_container.client:
                            with device_container:
                                device_container.clear()
            
            # Then set up new scenario if one is provided
            if scenario_name:
                # First check if scenario already exists
                container = Container.get_by_name(f"Smart Home - {scenario_name}")
                if not container:
                    logger.info(f"Creating new scenario: {scenario_name}")
                    # Create new scenario if it doesn't exist
                    container = self.smart_home_setup.create_scenario(scenario_name)
                else:
                    logger.info(f"Using existing scenario: {scenario_name}")
                
                if container:
                    # Set up the scenario
                    self.simulator.set_scenario(scenario_name)
                    self.active_scenario_id = container.id
                    
                    # Start the container
                    container.start(None)
                    
                    # Initialize simulators for all sensors
                    for device in container.devices:
                        for sensor in device.sensors:
                            if sensor.id not in self.sensor_simulators:
                                simulator = Simulator(sensor=sensor)
                                self.sensor_simulators[sensor.id] = simulator
                                logger.debug(f"Created simulator for sensor: {sensor.name} (ID: {sensor.id})")
                    
                    # Force an immediate update of the floor plan
                    self._update_smart_home()
                    logger.info(f"Successfully switched to scenario: {scenario_name}")
                else:
                    logger.error(f"Failed to create/activate scenario: {scenario_name}")
            else:
                logger.info("Scenario stopped")
                
        except Exception as e:
            logger.exception(f"Error in scenario change: {str(e)}")
            # Let the caller handle any UI notifications

    def _handle_motion_trigger(self):
        """Handle motion trigger events"""
        logger.info("Motion detected - Triggering lights")
        try:
            # This would typically interact with actual smart home devices
            # For simulation, we just show a notification
            ui.notify('Motion detected - Lights activated')
            logger.debug("Motion notification displayed")
        except Exception as e:
            logger.error(f"Error handling motion trigger: {str(e)}")

    def _handle_temperature_alert(self):
        """Handle temperature comfort alerts"""
        logger.info("Temperature alert triggered")
        try:
            ui.notify('Temperature outside comfort zone', type='warning')
            logger.debug("Temperature alert notification displayed")
        except Exception as e:
            logger.error(f"Error handling temperature alert: {str(e)}")

    def _update_alerts(self):
        """Update the alerts display"""
        try:
            if not self.alert_container or not self.alert_container.client:
                logger.debug("Alert container not available")
                return

            # Safely clear existing alerts
            try:
                self.alert_container.clear()
            except KeyError as e:
                logger.debug(f"Some elements were already removed: {e}")
            except Exception as e:
                logger.warning(f"Error clearing alert container: {e}")

            # Get active alerts
            alerts = []
            if self.active_scenario_id:
                container = Container.get_by_id(self.active_scenario_id)
                if container:
                    for device in container.devices:
                        for sensor in device.sensors:
                            if sensor.error_definition:
                                error_def = json.loads(sensor.error_definition)
                                error_type = error_def.get('type', 'unknown')
                                alerts.append({
                                    'device': device.name,
                                    'sensor': sensor.name,
                                    'error_type': error_type,
                                    'error_message': ERROR_MESSAGES.get(error_type, "Unknown error detected"),
                                    'details': {k: SENSOR_ERRORS_UI_MAP_EN.get(k, k) + f": {v}" 
                                              for k, v in error_def.items() 
                                              if k != 'type'}
                                })

            # Display alerts
            with self.alert_container:
                if not alerts:
                    ui.label('No active alerts').classes('text-gray-500')
                else:
                    for alert in alerts:
                        with ui.card().classes('w-full p-4 bg-red-50 mb-2'):
                            # Alert header
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('warning').classes('text-red-500')
                                ui.label(f"{alert['device']} - {alert['sensor']}").classes('font-bold text-red-600')
                            
                            # Main error message
                            ui.label(alert['error_message']).classes('text-sm text-red-600 mt-2')
                            
                            # Error details in an expansion panel
                            if alert['details']:
                                with ui.expansion('Details', icon='info').classes('w-full mt-2'):
                                    for detail in alert['details'].values():
                                        ui.label(detail).classes('text-sm text-red-500')

        except Exception as e:
            logger.exception(f"Error updating alerts: {str(e)}")
            # Try to show error in UI if possible
            try:
                with self.alert_container:
                    ui.label('Error updating alerts').classes('text-red-500')
            except:
                pass

    def _stop_scenario(self, container_id: int):
        """Stop a running scenario"""
        try:
            logger.info(f"Stopping scenario with container ID: {container_id}")
            container = Container.get_by_id(container_id)
            if container:
                # Stop the container
                container.stop()
                
                # Clear active scenario ID if it's the current one
                if self.active_scenario_id == container_id:
                    self.active_scenario_id = None
                    
                # Clear simulators for this container's sensors
                for device in container.devices:
                    for sensor in device.sensors:
                        if sensor.id in self.sensor_simulators:
                            del self.sensor_simulators[sensor.id]
                
                # Clear floor plan data and force refresh
                for room_type in ROOM_TYPES:
                    if room_type in self.floor_plan.rooms:
                        room = self.floor_plan.rooms[room_type]
                        room['ui_initialized'] = False
                        if room['device_container']:
                            room['device_container'].clear()
                
                # Clear scenario panel
                self.scenario_panel._update_scenario(None)
                
                # Force refresh of setups list
                self._update_setups_list()
                
                # Force an immediate update of the floor plan
                self._update_smart_home()
                
                logger.info(f"Successfully stopped scenario: {container.name}")
                ui.notify(f'Stopped {container.name}', type='warning')
            else:
                logger.warning(f"Container {container_id} not found")
                
        except Exception as e:
            logger.exception(f"Error stopping scenario: {str(e)}")
            ui.notify(f'Error stopping scenario: {str(e)}', type='negative')

    def _start_scenario(self, container_id: int):
        """Start a scenario"""
        try:
            logger.info(f"Starting scenario with container ID: {container_id}")
            container = Container.get_by_id(container_id)
            if container:
                # Stop any currently active scenario
                if self.active_scenario_id and self.active_scenario_id != container_id:
                    self._stop_scenario(self.active_scenario_id)
                
                # Start the container
                container.start(None)
                self.active_scenario_id = container_id
                
                # Initialize simulators for all sensors
                for device in container.devices:
                    for sensor in device.sensors:
                        if sensor.id not in self.sensor_simulators:
                            simulator = Simulator(sensor=sensor)
                            self.sensor_simulators[sensor.id] = simulator
                            logger.debug(f"Created simulator for sensor: {sensor.name} (ID: {sensor.id})")
                
                # Update scenario panel
                scenario_name = container.name.replace('Smart Home - ', '')
                self.scenario_panel._update_scenario(scenario_name)
                
                # Force refresh of setups list
                self._update_setups_list()
                
                # Force an immediate update of the floor plan
                self._update_smart_home()
                
                logger.info(f"Successfully started scenario: {container.name}")
                ui.notify(f'Started {container.name}', type='success')
            else:
                logger.warning(f"Container {container_id} not found")
                
        except Exception as e:
            logger.exception(f"Error starting scenario: {str(e)}")
            ui.notify(f'Error starting scenario: {str(e)}', type='negative')

    def _delete_scenario(self, container_id: int):
        """Delete a scenario setup"""
        try:
            # Get the container name before deletion
            container = Container.get_by_id(container_id)
            if not container:
                ui.notify('Container not found', type='negative')
                return
            
            scenario_name = container.name.replace('Smart Home - ', '')
            
            # Clean up the scenario
            self.smart_home_setup.cleanup_scenario(scenario_name)
            
            # If this was the active scenario, clear the active scenario ID
            if container_id == self.active_scenario_id:
                self.active_scenario_id = None
            
            ui.notify('Scenario deleted successfully', type='positive')
            self._update_setups_list()
        except Exception as e:
            ui.notify(f'Error deleting scenario: {str(e)}', type='negative')

    def _update_setups_list(self):
        """Update the list of existing scenario setups"""
        try:
            if not self.setups_container or not self.setups_container.client:
                return
            
            self.setups_container.clear()
            
            scenarios = self.smart_home_setup.list_scenarios()
            if not scenarios:
                with self.setups_container:
                    ui.label('No scenarios available').classes('text-gray-500')
                return
            
            with self.setups_container:
                for scenario in scenarios:
                    with ui.card().classes('w-full p-4 mb-2'):
                        with ui.row().classes('w-full items-center justify-between'):
                            with ui.column():
                                # Add active indicator
                                if scenario['is_active']:
                                    ui.label(f"🟢 {scenario['name']} (Active)").classes('font-bold text-green-600')
                                else:
                                    ui.label(scenario['name']).classes('font-bold')
                                ui.label(scenario['description']).classes('text-sm text-gray-600')
                                if scenario['id']:  # If scenario is created
                                    ui.label(f"Devices: {scenario['device_count']}, Sensors: {scenario['sensor_count']}").classes('text-sm')
                            with ui.row().classes('gap-2'):
                                if scenario['id']:  # If scenario is created
                                    if not scenario['is_active']:
                                        ui.button('Start', 
                                                on_click=lambda s=scenario: self._handle_scenario_action(
                                                    lambda: self._start_scenario(s['id'])))\
                                            .classes('bg-green-500 text-white')\
                                            .props('no-caps')
                                    else:
                                        ui.button('Stop', 
                                                on_click=lambda s=scenario: self._handle_scenario_action(
                                                    lambda: self._stop_scenario(s['id'])))\
                                            .classes('bg-red-500 text-white')\
                                            .props('no-caps')
                                    ui.button('Delete', 
                                            on_click=lambda s=scenario: self._handle_scenario_action(
                                                lambda: self._delete_scenario(s['id'])))\
                                        .classes('bg-gray-500 text-white')\
                                        .props('no-caps')
                                else:  # If scenario is not created yet
                                    ui.button('Create', 
                                            on_click=lambda n=scenario['name']: self._handle_scenario_action(
                                                lambda: self._activate_scenario(n)))\
                                        .classes('bg-blue-500 text-white')\
                                        .props('no-caps')
            
            # Force update of the container
            if self.setups_container.client:
                self.setups_container.update()
            
        except Exception as e:
            logger.exception(f"Error updating setups list: {str(e)}")

    def _handle_scenario_action(self, action):
        """Handle scenario action and refresh UI"""
        try:
            # Execute the action (start/stop/delete/create)
            action()
            
            # Force a client-side page refresh
            ui.run_javascript('window.location.reload();')
            
        except Exception as e:
            logger.exception(f"Error handling scenario action: {str(e)}")
            ui.notify(f'Error: {str(e)}', type='negative')

    def cleanup(self):
        """Cleanup resources when page is closed"""
        if self.update_timer:
            self.update_timer.active = False
        for simulator in self.sensor_simulators.values():
            if hasattr(simulator, 'stop'):
                simulator.stop() 