from nicegui import ui
from ui.floor_plan import FloorPlan
from ui.scenario_panel import ScenarioPanel
from utils.event_system import EventSystem, SmartHomeEvent, EventTrigger
from utils.smart_home_simulator import SmartHomeSimulator
from constants.device_templates import DEVICE_TEMPLATES
import asyncio

class SmartHomePage:
    """Smart home monitoring and control page"""
    
    def __init__(self):
        self.floor_plan = FloorPlan()
        self.event_system = EventSystem()
        self.simulator = SmartHomeSimulator()
        self.scenario_panel = ScenarioPanel(on_scenario_change=self._handle_scenario_change)
        self.alert_container = None
        
        # Setup default events
        self._setup_default_events()

    def create_page(self):
        """Create the smart home page"""
        with ui.row().classes('w-full justify-between'):
            with ui.column().classes('w-2/3'):
                # Floor plan view
                self.floor_plan.create_floor_plan()
            
            with ui.column().classes('w-1/3'):
                # Scenario control panel
                self.scenario_panel.create_panel()
                
                # Alerts panel
                with ui.card().classes('w-full q-mt-md'):
                    ui.label('Active Alerts').classes('text-h6')
                    self.alert_container = ui.column().classes('w-full')
        
        # Start update timer
        ui.timer(5.0, self._update_smart_home)

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
        self.simulator.set_scenario(scenario_name)
        ui.notify(f'Switched to {scenario_name} scenario')

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
        if not self.alert_container:
            return
            
        with self.alert_container:
            self.alert_container.clear()
            active_emergencies = self.event_system.get_active_emergencies()
            if not active_emergencies:
                ui.label('No active alerts')
                return
            
            for emergency in active_emergencies:
                with ui.card().classes('w-full bg-red-100 q-pa-sm q-mb-sm'):
                    ui.label(f"{emergency.name} - {emergency.severity.upper()}").classes('text-red text-bold')
                    if emergency.start_time:
                        ui.label(f"Started: {emergency.start_time.strftime('%H:%M:%S')}").classes('text-sm')

    def _update_smart_home(self):
        """Update the smart home system state"""
        try:
            # Process scheduled scenarios
            self.scenario_panel.process_scheduled_scenarios()
            
            # Update alerts
            self._update_alerts()
            
            # Simulate sensor updates (in a real system, this would come from actual sensors)
            # This is just for demonstration
            for room_type in self.floor_plan.rooms:
                devices = []
                for template_name, template in DEVICE_TEMPLATES.items():
                    device = {
                        'name': template_name,
                        'sensors': []
                    }
                    
                    for sensor in template['sensors']:
                        # Generate simulated value
                        base_value = (sensor['max'] - sensor['min']) / 2 + sensor['min']
                        value = self.simulator.adjust_sensor_value(base_value, sensor['type'])
                        
                        device['sensors'].append({
                            'name': sensor['name'],
                            'type': sensor['type'],
                            'value': value,
                            'unit': sensor['unit'] if 'unit' in sensor else ''
                        })
                        
                        # Process events based on sensor update
                        self.event_system.process_sensor_update(sensor['type'], value, room_type)
                    
                    devices.append(device)
                
                # Update room display
                self.floor_plan.update_room_data(room_type, devices)
        except Exception as e:
            print(f"Error in update: {str(e)}")
            
        return True  # Keep the timer running 