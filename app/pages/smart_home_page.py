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
import asyncio

class SmartHomePage:
    """Smart home monitoring and control page"""
    
    def __init__(self):
        self.floor_plan = FloorPlan()
        self.event_system = EventSystem()
        self.simulator = SmartHomeSimulator()
        self.smart_home_setup = SmartHomeSetup()
        self.scenario_panel = ScenarioPanel(on_scenario_change=self._handle_scenario_change)
        self._setup_default_events()
        self.alert_container = None
        self.active_scenario_id = None
        self.sensor_simulators = {}  # Store simulators by sensor ID

    def create_page(self):
        """Create the smart home page"""
        with ui.column().classes('w-full gap-4'):
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

        # Start update timer
        ui.timer(5.0, self._update_smart_home)

    def _activate_scenario(self, scenario_name: str):
        """Activate a specific scenario"""
        try:
            # First, stop any active scenario
            if self.active_scenario_id is not None:
                self._stop_scenario(self.active_scenario_id)
            
            # Create and start the new scenario
            container = self.smart_home_setup.create_scenario(scenario_name)
            if not container:
                ui.notify(f'Failed to create scenario: {scenario_name}', type='negative')
                return
            
            self.active_scenario_id = container.id
            self._start_scenario(container.id)
            
            # Update the scenario panel
            self.scenario_panel._update_scenario(scenario_name)
            
            # Refresh all pages
            from main import pages
            
            # Refresh each page
            if 'containers' in pages:
                pages['containers'].update_stats()
                pages['containers'].setup_cards_grid()
            if 'devices' in pages:
                pages['devices'].refresh_device_list()
                pages['devices'].update_stats()
            if 'sensors' in pages:
                pages['sensors'].update_stats()
                pages['sensors'].setup_list()
            
            ui.notify(f'Activated {scenario_name} scenario', type='positive')
        except Exception as e:
            ui.notify(f'Error activating scenario: {str(e)}', type='negative')

    def _update_smart_home(self):
        """Update the smart home display"""
        try:
            # Process any scheduled scenarios
            self.scenario_panel.process_scheduled_scenarios()
            
            # Update alerts
            self._update_alerts()
            
            # Update floor plan
            if self.active_scenario_id:
                container = Container.get_by_id(self.active_scenario_id)
                if container:
                    # Group devices by room
                    room_devices = {}
                    for device in container.devices:
                        # Extract room name from device name (e.g., "Living Room - Environmental Monitor")
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
                            
                            # Add sensor data
                            for sensor in device.sensors:
                                try:
                                    # Get or create simulator for this sensor
                                    simulator = self.sensor_simulators.get(sensor.id)
                                    if simulator is None:
                                        simulator = Simulator(sensor=sensor)
                                        self.sensor_simulators[sensor.id] = simulator
                                    
                                    # Generate new data
                                    current_data = simulator.generate_data()
                                    
                                    # Extract current value, falling back to base value if needed
                                    current_value = current_data.get('value', sensor.base_value)
                                    if current_value is None:
                                        current_value = sensor.base_value
                                    
                                    # Update sensor data
                                    sensor_data = {
                                        'name': sensor.name,
                                        'base_value': sensor.base_value,
                                        'current_value': current_value,
                                        'unit': sensor.unit
                                    }
                                    device_data['sensors'].append(sensor_data)
                                    
                                    # Process any events based on the new value
                                    self.event_system.process_sensor_update(sensor.unit, current_value, room_name)
                                    
                                except Exception as e:
                                    # Use base value as fallback
                                    sensor_data = {
                                        'name': sensor.name,
                                        'base_value': sensor.base_value,
                                        'current_value': sensor.base_value,
                                        'unit': sensor.unit
                                    }
                                    device_data['sensors'].append(sensor_data)
                            
                            room_devices[room_name].append(device_data)
                    
                    # Update each room in the floor plan
                    for room_name, devices in room_devices.items():
                        self.floor_plan.update_room_data(room_name, devices)
            
            return True  # Keep the timer running
        except Exception as e:
            print(f"Error updating smart home: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return True  # Keep the timer running even if there's an error

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

    def _handle_scenario_change(self, scenario_name: str):
        """Handle scenario changes"""
        try:
            # First clean up any existing scenario
            if self.active_scenario_id:
                # Clear old scenario
                old_container = Container.get_by_id(self.active_scenario_id)
                if old_container:
                    old_container.stop()  # Stop the old container
                    
                self.simulator.set_scenario(None)
                self.active_scenario_id = None
                self.sensor_simulators.clear()  # Clear all sensor simulators
                
                # Clear all room displays
                for room_type in ROOM_TYPES:
                    if room_type in self.floor_plan.rooms:
                        device_container = self.floor_plan.rooms[room_type]['device_container']
                        if device_container:
                            device_container.clear()
            
            # Then set up new scenario if one is provided
            if scenario_name:
                # First check if scenario already exists
                container = Container.get_by_name(f"Smart Home - {scenario_name}")
                if not container:
                    # Create new scenario if it doesn't exist
                    container = self.smart_home_setup.create_scenario(scenario_name)
                
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
                    
                    # Force an immediate update of the floor plan
                    self._update_smart_home()
                    ui.notify(f'Switched to {scenario_name} scenario')
                else:
                    ui.notify(f'Failed to create/activate scenario: {scenario_name}', type='error')
            else:
                ui.notify('Scenario stopped')
                
        except Exception as e:
            print(f"Error in scenario change: {str(e)}")
            import traceback
            print(traceback.format_exc())
            ui.notify(f'Error changing scenario: {str(e)}', type='error')

    def _handle_motion_trigger(self):
        """Handle motion trigger events"""
        # This would typically interact with actual smart home devices
        # For simulation, we just show a notification
        ui.notify('Motion detected - Lights activated')

    def _handle_temperature_alert(self):
        """Handle temperature comfort alerts"""
        ui.notify('Temperature outside comfort zone', type='warning')

    def _update_alerts(self):
        """Update the alerts panel"""
        try:
            if not self.alert_container or not self.alert_container.client:
                return
            
            self.alert_container.clear()
            active_emergencies = self.event_system.get_active_emergencies()
            if not active_emergencies:
                with self.alert_container:
                    ui.label('No active alerts')
                return
            
            with self.alert_container:
                for emergency in active_emergencies:
                    with ui.card().classes('w-full bg-red-100 q-pa-sm q-mb-sm'):
                        ui.label(f"{emergency.name} - {emergency.severity.upper()}").classes('text-red text-bold')
                        if emergency.start_time:
                            ui.label(f"Started: {emergency.start_time.strftime('%H:%M:%S')}").classes('text-sm')
        except Exception as e:
            print(f"Error updating alerts: {str(e)}")

    def _start_scenario(self, container_id: int):
        """Start a scenario setup"""
        try:
            container = Container.get_by_id(container_id)
            if container:
                # Get scenario name from container name
                scenario_name = container.name.replace('Smart Home - ', '')
                
                # First clean up any existing scenario
                if self.active_scenario_id:
                    old_container = Container.get_by_id(self.active_scenario_id)
                    if old_container:
                        old_container.stop()
                    self.simulator.set_scenario(None)
                    self.active_scenario_id = None
                    self.sensor_simulators.clear()
                
                # Set up the new scenario
                self.simulator.set_scenario(scenario_name)
                self.active_scenario_id = container.id
                
                # Start the container
                container.start(None)  # Pass None for interface to use default
                
                # Initialize simulators for all sensors
                for device in container.devices:
                    for sensor in device.sensors:
                        if sensor.id not in self.sensor_simulators:
                            simulator = Simulator(sensor=sensor)
                            self.sensor_simulators[sensor.id] = simulator
                
                # Force an immediate update of the floor plan
                self._update_smart_home()
                
                ui.notify(f'Started scenario: {container.name}', type='positive')
                self._update_setups_list()
                
        except Exception as e:
            print(f"Error starting scenario: {str(e)}")
            import traceback
            print(traceback.format_exc())
            ui.notify(f'Error starting scenario: {str(e)}', type='negative')

    def _stop_scenario(self, container_id: int):
        """Stop a scenario setup"""
        try:
            container = Container.get_by_id(container_id)
            if container:
                # Stop the container
                container.stop()
                
                # Clear scenario from simulator
                if container_id == self.active_scenario_id:
                    self.simulator.set_scenario(None)
                    self.active_scenario_id = None
                    
                    # Clear all sensor simulators
                    self.sensor_simulators.clear()
                    
                    # Clear all room displays in floor plan
                    for room_type in ROOM_TYPES:
                        if room_type in self.floor_plan.rooms:
                            device_container = self.floor_plan.rooms[room_type]['device_container']
                            if device_container and device_container.client:
                                with device_container:
                                    device_container.clear()
                
                ui.notify(f'Stopped scenario: {container.name}', type='positive')
                self._update_setups_list()
                
        except Exception as e:
            print(f"Error stopping scenario: {str(e)}")
            import traceback
            print(traceback.format_exc())
            ui.notify(f'Error stopping scenario: {str(e)}', type='negative')

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
                                        ui.button('Start', on_click=lambda s=scenario: self._start_scenario(s['id'])).classes('bg-green-500 text-white')
                                    else:
                                        ui.button('Stop', on_click=lambda s=scenario: self._stop_scenario(s['id'])).classes('bg-red-500 text-white')
                                    ui.button('Delete', on_click=lambda s=scenario: self._delete_scenario(s['id'])).classes('bg-gray-500 text-white')
                                else:  # If scenario is not created yet
                                    ui.button('Create', on_click=lambda n=scenario['name']: self._activate_scenario(n)).classes('bg-blue-500 text-white')
        except Exception as e:
            print(f"Error updating setups list: {str(e)}")

    def _handle_motion_trigger(self):
        """Handle motion trigger events"""
        # This would typically interact with actual smart home devices
        # For simulation, we just show a notification
        ui.notify('Motion detected - Lights activated')

    def _handle_temperature_alert(self):
        """Handle temperature comfort alerts"""
        ui.notify('Temperature outside comfort zone', type='warning')

    def _update_alerts(self):
        """Update the alerts panel"""
        try:
            if not self.alert_container or not self.alert_container.client:
                return
            
            self.alert_container.clear()
            active_emergencies = self.event_system.get_active_emergencies()
            if not active_emergencies:
                with self.alert_container:
                    ui.label('No active alerts')
                return
            
            with self.alert_container:
                for emergency in active_emergencies:
                    with ui.card().classes('w-full bg-red-100 q-pa-sm q-mb-sm'):
                        ui.label(f"{emergency.name} - {emergency.severity.upper()}").classes('text-red text-bold')
                        if emergency.start_time:
                            ui.label(f"Started: {emergency.start_time.strftime('%H:%M:%S')}").classes('text-sm')
        except Exception as e:
            print(f"Error updating alerts: {str(e)}")

    def _update_smart_home(self):
        """Update the smart home display"""
        try:
            # Process any scheduled scenarios
            self.scenario_panel.process_scheduled_scenarios()
            
            # Update alerts
            self._update_alerts()
            
            # Update floor plan
            if self.active_scenario_id:
                container = Container.get_by_id(self.active_scenario_id)
                if container:
                    # Group devices by room
                    room_devices = {}
                    for device in container.devices:
                        # Extract room name from device name (e.g., "Living Room - Environmental Monitor")
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
                            
                            # Add sensor data
                            for sensor in device.sensors:
                                try:
                                    # Get or create simulator for this sensor
                                    simulator = self.sensor_simulators.get(sensor.id)
                                    if simulator is None:
                                        simulator = Simulator(sensor=sensor)
                                        self.sensor_simulators[sensor.id] = simulator
                                    
                                    # Generate new data
                                    current_data = simulator.generate_data()
                                    
                                    # Extract current value, falling back to base value if needed
                                    current_value = current_data.get('value', sensor.base_value)
                                    if current_value is None:
                                        current_value = sensor.base_value
                                    
                                    # Update sensor data
                                    sensor_data = {
                                        'name': sensor.name,
                                        'base_value': sensor.base_value,
                                        'current_value': current_value,
                                        'unit': sensor.unit
                                    }
                                    device_data['sensors'].append(sensor_data)
                                    
                                    # Process any events based on the new value
                                    self.event_system.process_sensor_update(sensor.unit, current_value, room_name)
                                    
                                except Exception as e:
                                    # Use base value as fallback
                                    sensor_data = {
                                        'name': sensor.name,
                                        'base_value': sensor.base_value,
                                        'current_value': sensor.base_value,
                                        'unit': sensor.unit
                                    }
                                    device_data['sensors'].append(sensor_data)
                            
                            room_devices[room_name].append(device_data)
                    
                    # Update each room in the floor plan
                    for room_name, devices in room_devices.items():
                        self.floor_plan.update_room_data(room_name, devices)
            
            return True  # Keep the timer running
        except Exception as e:
            print(f"Error updating smart home: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return True  # Keep the timer running even if there's an error 