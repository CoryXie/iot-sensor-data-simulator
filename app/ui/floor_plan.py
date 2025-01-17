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

    def _create_room_card(self, room_name: str):
        """Create a card for a room"""
        self.rooms[room_name] = {
            'devices': [],
            'alerts': []
        }
        
        with ui.card().classes('w-full'):
            ui.label(room_name).classes('text-h6')
            
            # Container for device status
            device_container = ui.column().classes('w-full')
            self.rooms[room_name]['device_container'] = device_container
            
            # Container for alerts
            alert_container = ui.column().classes('w-full')
            self.rooms[room_name]['alert_container'] = alert_container

    def update_room_data(self, room_name: str, devices: List[Dict]):
        """Update the room data display"""
        if room_name not in self.rooms:
            return
            
        device_container = self.rooms[room_name]['device_container']
        alert_container = self.rooms[room_name]['alert_container']
        
        with device_container:
            device_container.clear()
            for device in devices:
                with ui.card().classes('w-full p-2 mb-2'):
                    ui.label(device['name']).classes('font-bold')
                    for sensor in device['sensors']:
                        with ui.row().classes('justify-between'):
                            ui.label(f"{sensor['name']}:")
                            ui.label(f"{sensor['value']:.1f} {sensor['unit']}")
        
        with alert_container:
            alert_container.clear()
            room_alerts = [alert for alert in self.alerts if alert['room'] == room_name]
            for alert in room_alerts:
                with ui.card().classes('w-full p-2 mb-2bg-red-100'):
                    ui.label(alert['message']).classes('text-red-600')

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
        with alert_container:
            alert_container.clear()
            room_alerts = [alert for alert in self.alerts if alert['room'] == room_name]
            for alert in room_alerts:
                with ui.card().classes('w-full p-2 mb-2 bg-red-100'):
                    ui.label(alert['message']).classes('text-red-600')

    def clear_alerts(self, room_name: str = None):
        """Clear alerts for a room or all rooms"""
        if room_name:
            self.alerts = [alert for alert in self.alerts if alert['room'] != room_name]
            alert_container = self.rooms[room_name]['alert_container']
            with alert_container:
                alert_container.clear()
        else:
            self.alerts = []
            for room in self.rooms.values():
                with room['alert_container']:
                    room['alert_container'].clear() 