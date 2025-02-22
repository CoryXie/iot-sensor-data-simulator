import json
from src.utils.logger import logger
from nicegui import ui
from src.database import SessionLocal
from src.models.room import Room
from src.models.device import Device
from src.models.sensor import Sensor
from src.utils.smart_home_simulator import SmartHomeSimulator
from src.utils.event_system import EventSystem
from typing import Dict, List
import asyncio
from sqlalchemy.orm import joinedload

class FloorPlan:
    def __init__(self, event_system: EventSystem = None):
        """Initialize FloorPlan component
        
        Args:
            event_system: Optional event system instance. If not provided, a new one will be created.
        """
        self.event_system = event_system or EventSystem()
        self.simulator = SmartHomeSimulator(self.event_system)
        self.rooms: Dict[str, Room] = {}
        self.sensor_displays: Dict[str, ui.label] = {}
        self.db = SessionLocal
        self._load_rooms()
        
    async def update_sensor_values(self):
        """Update sensor values in real-time"""
        while True:
            try:
                with self.db() as session:  # Use context manager for database session
                    for sensor_id, display in self.sensor_displays.items():
                        sensor = session.query(Sensor).get(sensor_id)
                        if sensor:
                            value = sensor.current_value  # Use the sensor's current value
                            if isinstance(value, (int, float)):
                                display.text = f"{value:.1f}{sensor.unit}"
                            else:
                                display.text = str(value)
            except Exception as e:
                logger.error(f"Error updating sensor values: {e}")
            await asyncio.sleep(1)  # Update every second

    def get_sensor_icon(self, sensor_type: str) -> str:
        """Map sensor types to appropriate icons"""
        return {
            'temperature': 'thermostat',
            'humidity': 'water_drop',
            'motion': 'motion_sensor',
            'light': 'lightbulb_outline',
            'door': 'door_sensor',
            'window': 'window_closed',
            'smoke': 'smoke_detector',
            'air_quality': 'airwave',
            'water': 'water_damage',
            'energy': 'flash_on'
        }.get(sensor_type.lower(), 'sensors')

    def create_floor_plan(self):
        """Generate floor plan visualization"""
        with ui.grid(columns=3).classes('w-full gap-4'):
            for room_name, room_data in self.rooms.items():
                with ui.card().classes('room-card p-4 w-full h-80'):
                    ui.label(room_name).classes('text-xl font-bold mb-4')
                    with ui.scroll_area().classes('w-full h-full'):
                        with ui.column().classes('w-full space-y-2'):
                            for device in room_data['devices']:
                                with ui.card().classes('device-card p-2 w-full'):
                                    with ui.row().classes('items-center'):
                                        ui.icon('devices').classes('text-2xl mr-2')
                                        ui.label(device['name'])
                                    with ui.row().classes('pl-8 space-x-2'):
                                        for sensor in device['sensors']:
                                            with ui.card().classes('sensor-chip p-1 px-2'):
                                                ui.label(f"{sensor['name']}: {sensor['value']}{sensor['unit']}")

    def update_room_data(self, room_type: str, devices: list, sensors: list = None):
        """Update room content with real devices and sensors"""
        if room_type not in self.rooms:
            return

        room = self.rooms[room_type]
        room['content'].clear()
        
        with room['content']:
            if not devices:
                ui.label('No devices').classes('text-gray-400')
                return
            
            for device in devices:
                with ui.card().classes('w-full mb-2'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('devices').classes('text-xl')
                        ui.label(device['name']).classes('font-medium')
                        
                    # Device sensors
                    with ui.column().classes('pl-8'):
                        for sensor in device.get('sensors', []):
                            sensor_id = f"{device['id']}-{sensor['type']}"
                            with ui.row().classes('items-center gap-2'):
                                ui.icon(self._get_sensor_icon(sensor['type']))
                                ui.label(sensor['name'])
                                value_label = ui.label().classes('font-mono')
                                room['sensors'][sensor_id] = value_label

    def _get_sensor_icon(self, sensor_type: str) -> str:
        """Get appropriate sensor icon"""
        return {
            'temperature': 'thermostat',
            'humidity': 'water',
            'motion': 'directions_run',
            'light': 'lightbulb'
        }.get(sensor_type, 'sensors')

    def _load_rooms(self):
        """Load rooms with their associated devices and sensors"""
        with self.db() as session:
            rooms = session.query(Room).options(
                joinedload(Room.devices).joinedload(Device.sensors)
            ).all()
            
            self.rooms = {}
            for room in rooms:
                self.rooms[room.name] = {
                    'devices': [
                        {
                            'name': device.name,
                            'sensors': [
                                {
                                    'name': sensor.name,
                                    'value': sensor.current_value,
                                    'unit': sensor.unit,
                                    'type': sensor.type
                                }
                                for sensor in device.sensors
                            ]
                        }
                        for device in room.devices
                    ]
                }
            # Fix the sensor count calculation
            total_sensors = sum(
                len(device['sensors']) 
                for room_data in self.rooms.values() 
                for device in room_data['devices']
            )
            logger.debug(f"Loaded {len(rooms)} rooms with {total_sensors} sensors")

    def _handle_mqtt_update(self, msg):
        """Update sensor displays from MQTT messages"""
        try:
            data = json.loads(msg.payload)
            sensor_id = f"{data['device_id']}-{data['sensor_type']}"
            
            for room in self.rooms.values():
                if sensor_id in room['sensors']:
                    room['sensors'][sensor_id].text = f"{data['value']}{data['unit']}"
                    break
                
        except Exception as e:
            logger.error(f"Error handling MQTT update: {str(e)}") 

    def _setup_sensor_updates(self):
        """Setup sensor update event handling"""
        @self.event_system.on('sensor_update')
        def handle_sensor_update(event_name, sensor_data):
            room_type = sensor_data.get('room_type', 'unknown')
            device_type = sensor_data.get('device_type', 'generic')
            
            # Update corresponding room element
            if room_type in self.room_elements:
                room = self.room_elements[room_type]
                device_id = sensor_data['device_id']
                
                # Find or create device element
                device_element = next((d for d in room['devices'] if d['id'] == device_id), None)
                if not device_element:
                    device_element = {
                        'id': device_id,
                        'type': device_type,
                        'sensors': [],
                        'element': ui.icon('devices').classes('absolute')
                    }
                    room['devices'].append(device_element)
                
                # Update sensor value
                sensor_element = next((s for s in device_element['sensors'] 
                                    if s['name'] == sensor_data['name']), None)
                if not sensor_element:
                    sensor_element = {
                        'name': sensor_data['name'],
                        'value': ui.label().classes('text-xs')
                    }
                    device_element['sensors'].append(sensor_element)
                
                sensor_element['value'].set_text(
                    f"{sensor_data['value']}{sensor_data.get('unit', '')}"
                )
                
                # Update icon color based on status
                status_color = 'green' if sensor_data.get('status') == 'normal' else 'red'
                device_element['element'].classes(replace='text-' + status_color) 