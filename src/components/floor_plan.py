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
        """Create 3 rows with 2 rooms each using responsive grid"""
        with ui.column().classes('w-full h-full p-4 gap-4'):
            # Row 1
            with ui.grid(columns=2).classes('w-full h-1/3 gap-4'):
                for name in ['Living Room', 'Kitchen']:
                    if name in self.rooms:
                        self._create_room_ui(self.rooms[name])
            
            # Row 2
            with ui.grid(columns=2).classes('w-full h-1/3 gap-4'):
                for name in ['Bedroom', 'Bathroom']:
                    if name in self.rooms:
                        self._create_room_ui(self.rooms[name])
            
            # Row 3
            with ui.grid(columns=2).classes('w-full h-1/3 gap-4'):
                for name in ['Office', 'Garage']:
                    if name in self.rooms:
                        self._create_room_ui(self.rooms[name])

    def _create_room_ui(self, room: Room):
        """Create room UI with devices and sensors"""
        with ui.card().classes('room bg-blue-50 p-4 rounded-lg w-full'):
            # Room header
            ui.label(room.name).classes('text-xl font-bold mb-4')
            
            # Devices section
            with ui.column().classes('w-full mb-4 space-y-2'):
                ui.label('Devices').classes('text-sm font-semibold text-gray-600')
                for device in room.devices:
                    with ui.row().classes('items-center space-x-2 p-2 hover:bg-blue-100 rounded'):
                        ui.icon(device.icon or 'devices').classes('text-xl text-blue-600')
                        ui.label(device.name).classes('text-gray-700')
            
            # Sensors section
            with ui.grid(columns=2).classes('w-full gap-2'):
                for sensor in room.sensors:
                    with ui.card().classes('p-2 bg-white hover:shadow-md transition-shadow'):
                        with ui.row().classes('items-center justify-between'):
                            # Sensor icon and name
                            with ui.row().classes('items-center space-x-2'):
                                ui.icon(self.get_sensor_icon(sensor.type)).classes('text-2xl text-green-600')
                                ui.label(sensor.name).classes('font-medium')
                            
                            # Real-time value display
                            with ui.row().classes('items-center'):
                                ui.label().bind_text_from(
                                    sensor, 'current_value',
                                    lambda v, u=sensor.unit: f"{v} {u}"
                                ).classes('font-mono text-lg')
                                ui.spinner(size='sm').classes('ml-2').bind_visibility_from(
                                    sensor, 'current_value', lambda v: v is None
                                )

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
        """Load rooms from database with their devices and sensors"""
        with self.db() as session:
            rooms = session.query(Room).options(
                joinedload(Room.devices),
                joinedload(Room.sensors)
            ).all()
            
            self.rooms = {room.name: room for room in rooms}
            logger.debug(f"Loaded {len(self.rooms)} rooms for floor plan") 

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