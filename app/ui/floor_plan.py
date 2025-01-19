from nicegui import ui
from typing import Dict, List
from constants.device_templates import ROOM_TYPES
from datetime import datetime

class FloorPlan:
    """Floor plan visualization component"""
    def __init__(self):
        self.rooms: Dict[str, Dict] = {}
        self.alerts = []
        self.main_container = None
        
    def create_floor_plan(self):
        """Create the floor plan visualization"""
        with ui.card().classes('w-full') as self.main_container:
            ui.label('Smart Home Floor Plan').classes('text-h6')
            
            # Create grid layout for rooms
            with ui.grid(columns=3).classes('w-full gap-4 p-4'):
                for room_type in ROOM_TYPES:
                    self._create_room_card(room_type)

    def _create_room_card(self, room_type: str) -> None:
        """Create a card for a room type"""
        with ui.card().classes('w-full p-4 room-card') as card:
            ui.label(room_type).classes('text-h6 mb-2')
            
            # Create containers for devices and alerts
            with ui.column().classes('w-full mt-2 device-container') as device_container:
                pass
            with ui.column().classes('w-full mt-2 alert-container') as alert_container:
                pass
            
            self.rooms[room_type] = {
                'card': card,
                'device_container': device_container,
                'alert_container': alert_container,
                'devices': []
            }

    def _get_room_icon(self, room_name: str) -> str:
        """Get the appropriate icon for a room type"""
        icons = {
            'Living Room': 'living',
            'Kitchen': 'kitchen',
            'Bedroom': 'bedroom',
            'Bathroom': 'bathroom',
            'Office': 'computer',
            'Garage': 'garage'
        }
        return icons.get(room_name, 'home')

    def update_room_data(self, room_type: str, devices: list) -> None:
        """Update the data for a room"""
        if room_type not in self.rooms:
            return
        
        room = self.rooms[room_type]
        device_container = room['device_container']
        
        # Clear existing devices
        device_container.clear()
        
        # Add devices and their sensors
        for device in devices:
            with device_container:
                with ui.expansion(device['name'], icon='devices').classes('w-full'):
                    with ui.column().classes('w-full'):
                        for sensor in device['sensors']:
                            with ui.row().classes('w-full justify-between items-center'):
                                ui.label(f"{sensor['name']}:").classes('text-bold')
                                with ui.column().classes('text-right'):
                                    ui.label(f"Base: {sensor['base_value']:.1f} {sensor['unit']}").classes('text-sm')
                                    ui.label(f"Current: {sensor['current_value']:.1f} {sensor['unit']}").classes('text-sm text-primary')

    def _get_sensor_icon(self, sensor_name: str) -> str:
        """Get the appropriate icon for a sensor type"""
        icons = {
            'Temperature': 'thermostat',
            'Humidity': 'water_drop',
            'Air Quality': 'air',
            'Motion': 'motion_sensors',
            'Door Status': 'door_front',
            'Window Status': 'window',
            'Brightness': 'light_mode',
            'Color Temperature': 'palette',
            'Smoke Level': 'smoke_detector',
            'CO Level': 'co2',
            'Water Leak': 'water_damage'
        }
        return icons.get(sensor_name, 'sensors')

    def add_alert(self, room_name: str, message: str):
        """Add an alert to a room"""
        if room_name not in self.rooms:
            return
            
        self.alerts.append({
            'room': room_name,
            'message': message,
            'timestamp': datetime.now()
        })
        
        alert_container = self.rooms[room_name]['alert_container']
        if not alert_container:
            return
            
        alert_container.clear()
        with alert_container:
            room_alerts = [alert for alert in self.alerts if alert['room'] == room_name]
            if room_alerts:
                for alert in room_alerts:
                    with ui.card().classes('w-full p-2 bg-red-100'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('warning').classes('text-red-500')
                            ui.label(alert['message']).classes('text-red-600')
                            ui.label(f"({alert['timestamp'].strftime('%H:%M:%S')})").classes('text-sm text-red-400')

    def clear_alerts(self, room_name: str = None):
        """Clear alerts for a room or all rooms"""
        if room_name:
            self.alerts = [alert for alert in self.alerts if alert['room'] != room_name]
            alert_container = self.rooms[room_name]['alert_container']
            if alert_container:
                alert_container.clear()
        else:
            self.alerts = []
            for room in self.rooms.values():
                if 'alert_container' in room and room['alert_container']:
                    room['alert_container'].clear() 