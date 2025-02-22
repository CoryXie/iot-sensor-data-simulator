import json
from src.utils.logger import logger
from nicegui import ui
from src.database import SessionLocal
from src.models.room import Room
from src.models.device import Device
from src.models.sensor import Sensor
from src.utils.event_system import EventSystem
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, List
import asyncio
from sqlalchemy.orm import joinedload
import random
from datetime import datetime
import threading
import time

class FloorPlan:
    def __init__(self, event_system: EventSystem = None):
        """Initialize FloorPlan component"""
        self.event_system = event_system or EventSystem()
        self.room_elements = {}
        self.rooms: Dict[str, Room] = {}
        self.device_states = {}
        self.sensor_states = {}
        
        with SessionLocal() as session:
            rooms = session.query(Room).options(joinedload(Room.devices)).all()
            self.rooms = {room.room_type: room for room in rooms}
            
            # Initialize states with default values
            for room in rooms:
                for device in room.devices:
                    self.device_states[device.id] = {
                        'name': device.name,
                        'counter': device.update_counter or 0
                    }
                    for sensor in device.sensors:
                        initial_value = sensor.current_value if sensor.current_value is not None else self._get_default_value(sensor.type)
                        self.sensor_states[sensor.id] = {
                            'value': initial_value,
                            'unit': sensor.unit or self._get_default_unit(sensor.type),
                            'display_value': self._format_value_with_unit(initial_value, sensor.unit or self._get_default_unit(sensor.type))
                        }
            
            logger.info(f'Initialized {len(self.rooms)} rooms with devices')
            
        self.sensor_displays = {}
        self.room_labels = {}
        self.device_labels = {}
        self.device_elements = {}
        self.db = SessionLocal
        self.update_lock = asyncio.Lock()
        self._setup_event_handlers()

    def _get_default_value(self, sensor_type: str) -> float:
        """Get default value for a sensor type"""
        defaults = {
            "temperature": 22.0,    # Celsius
            "humidity": 50.0,       # Percentage
            "light": 500,           # Lux
            "motion": 0,            # Binary
            "air_quality": 100,     # AQI
            "co": 0.0,             # PPM
            "smoke": 0.0,          # PPM
            "gas": 0.0,            # PPM
            "water": 0             # Binary
        }
        return defaults.get(sensor_type.lower(), 0.0)

    def _get_default_unit(self, sensor_type: str) -> str:
        """Get default unit for a sensor type"""
        units = {
            "temperature": "°C",
            "humidity": "%",
            "light": "lux",
            "motion": "",
            "air_quality": "AQI",
            "co": "PPM",
            "smoke": "PPM",
            "gas": "PPM",
            "water": ""
        }
        return units.get(sensor_type.lower(), "")

    async def update_sensor_values(self, rooms_data: Dict[str, List[dict]]):
        """Update sensor values in real-time using provided rooms data"""
        start_time = time.time()
        logger.info(f"Starting sensor values update with {len(rooms_data)} rooms")
        logger.debug(f"Current sensor displays: {len(self.sensor_displays)} registered")
        
        try:
            async with self.update_lock:
                logger.debug("Acquired update lock")
                
                for room_type, devices_data in rooms_data.items():
                    logger.debug(f"Processing room: {room_type} with {len(devices_data)} devices")
                    
                    if room_type in self.room_elements:
                        room_card = self.room_elements[room_type]
                        logger.debug(f"Found room card for {room_type}")
                        
                        with room_card['container']:
                            logger.debug(f"Entered container context for {room_type}")
                            updates_count = 0
                            
                            for device_data in devices_data:
                                device_name = device_data.get('name', '')
                                sensors_data = device_data.get('sensors', [])
                                logger.debug(f"Processing device: {device_name} with {len(sensors_data)} sensors")
                                
                                for sensor_data in sensors_data:
                                    sensor_id = sensor_data.get('id')
                                    if sensor_id and sensor_id in self.sensor_displays:
                                        try:
                                            old_value = self.sensor_displays[sensor_id].text
                                            new_value = self._format_sensor_value_from_data(sensor_data)
                                            
                                            if old_value != new_value:
                                                logger.debug(f"Updating sensor {sensor_id} ({sensor_data.get('name', '')}) from {old_value} to {new_value}")
                                                self.sensor_displays[sensor_id].set_text(new_value)
                                                updates_count += 1
                                            else:
                                                logger.debug(f"Sensor {sensor_id} value unchanged: {old_value}")
                                                
                                        except Exception as e:
                                            logger.error(f"Error updating sensor {sensor_id} ({sensor_data.get('name', '')}): {e}")
                                            logger.exception("Detailed error trace:")
                                    else:
                                        if sensor_id:
                                            logger.warning(f"Sensor {sensor_id} ({sensor_data.get('name', '')}) not found in displays dictionary")
                            
                            logger.info(f"Updated {updates_count} sensors in room {room_type}")
                    else:
                        logger.warning(f"Room {room_type} not found in UI elements")
                
                end_time = time.time()
                logger.info(f"Completed sensor updates in {(end_time - start_time):.2f} seconds")
                
        except Exception as e:
            logger.error(f"Error updating sensor values: {e}")
            logger.exception("Detailed error trace:")

    def _format_sensor_value_from_data(self, sensor_data: dict) -> str:
        """Format sensor value with unit from sensor data dictionary"""
        # Try 'value' first, then fall back to 'current_value' for backward compatibility
        value = sensor_data.get('value', sensor_data.get('current_value', 0.0))
        unit = sensor_data.get('unit', '')
        
        # Format numeric values to 2 decimal places if they're floats
        if isinstance(value, (float, int)):
            formatted_value = f"{float(value):.2f}"
        else:
            formatted_value = str(value)
            
        return f"{formatted_value}{unit}" if unit else formatted_value

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

    def create_floor_plan(self, container=None):
        """Generate floor plan visualization with data binding"""
        try:
            grid_container = container or ui.grid(columns=3).classes("gap-4 room-card-container")
            
            with grid_container:
                # Clear existing elements
                self.room_elements.clear()
                self.sensor_displays.clear()
                self.device_elements.clear()  # Clear device elements
                
                # Create room cards
                for room_type, room in self.rooms.items():
                    with ui.card().classes('room-card p-4') as room_container:
                        # Room header
                        ui.label(f"{room.name}").classes('text-h6 mb-2')
                        
                        # Create devices section
                        with ui.column().classes('w-full') as devices_container:
                            for device in room.devices:
                                # Initialize device state if not exists
                                if device.id not in self.device_states:
                                    self.device_states[device.id] = {
                                        'name': device.name,
                                        'counter': device.update_counter or 0,
                                        'sensors': {}
                                    }
                                
                                # Device card with relative positioning for bubble counter
                                with ui.card().classes('device-card p-2 mb-2 relative') as device_card:
                                    # Create counter element
                                    counter = ui.label(str(self.device_states[device.id]['counter']))
                                    counter.classes('absolute -top-2 -right-2 bg-primary text-white rounded-full min-w-[1.5rem] h-6 flex items-center justify-center text-xs')
                                    
                                    # Store device elements
                                    self.device_elements[device.id] = {
                                        'card': device_card,
                                        'counter': counter
                                    }
                                    
                                    ui.label(f"{device.name}").classes('text-subtitle1')
                                    
                                    # Create sensor displays
                                    for sensor in device.sensors:
                                        # Initialize sensor state if not exists
                                        if sensor.id not in self.sensor_states:
                                            initial_value = sensor.current_value if sensor.current_value is not None else self._get_default_value(sensor.type)
                                            self.sensor_states[sensor.id] = {
                                                'value': initial_value,
                                                'unit': sensor.unit or self._get_default_unit(sensor.type),
                                                'display_value': self._format_value_with_unit(initial_value, sensor.unit or self._get_default_unit(sensor.type))
                                            }
                                        
                                        with ui.row().classes('items-center gap-2'):
                                            icon = self.get_sensor_icon(sensor.type)
                                            ui.icon(icon).classes('text-primary')
                                            ui.label(f"{sensor.name}:").classes('font-medium')
                                            
                                            # Bind sensor value display
                                            display = ui.label(self.sensor_states[sensor.id]['display_value'])
                                            self.sensor_displays[sensor.id] = display
                        
                        # Store room elements for future updates
                        self.room_elements[room_type] = {
                            'container': room_container,
                            'devices_container': devices_container,
                            'devices': []
                        }
                        
            logger.info(f"Created floor plan with {len(self.rooms)} rooms and {len(self.sensor_displays)} sensors")
            logger.debug(f"Device elements: {list(self.device_elements.keys())}")
                
        except Exception as e:
            logger.error(f"Error creating floor plan: {e}")
            raise

    def _format_value_with_unit(self, value, unit):
        """Format value with unit for display"""
        if isinstance(value, (int, float)):
            return f"{value:.1f}{unit}"
        return f"{value}{unit}"

    def _format_sensor_value(self, sensor) -> str:
        """Format sensor value with unit"""
        value = sensor.current_value
        unit = self._get_sensor_unit(sensor.type)
        if isinstance(value, (int, float)):
            return f"{value:.1f}{unit}"
        return f"{value}{unit}"

    def _get_sensor_unit(self, sensor_type: str) -> str:
        """Get the appropriate unit for sensor type"""
        return {
            'temperature': '°C',
            'humidity': '%',
            'light': 'lux',
            'motion': '',
            'co2': 'ppm',
            'pressure': 'hPa',
            'noise': 'dB',
        }.get(sensor_type.lower(), '')

    async def update_room_data(self, room_type: str) -> None:
        """Update room card with latest sensor data and device states"""
        try:
            # Validate input
            if not room_type or not isinstance(room_type, str):
                raise ValueError(f"Invalid room name: {room_type}")

            # Get fresh database session
            with SessionLocal() as session:
                # Get complete room state
                room = session.query(Room)\
                    .options(joinedload(Room.devices).joinedload(Device.sensors))\
                    .filter(Room.room_type == room_type)\
                    .first()

                if not room:
                    logger.error(f"Room not found: {room_type}")
                    return

                # Update UI components
                with ui.card().classes(self.room_card_classes) as card:
                    # Sensor displays
                    self._update_sensor_displays(card, room.sensors)

                    # Device controls
                    self._update_device_controls(card, room.devices)

                # Cache latest state
                self.rooms[room_name] = {
                    'ui': card,
                    'last_updated': datetime.now(),
                    'sensor_values': {s.id: s.value for s in room.sensors},
                    'device_states': {d.id: d.status for d in room.devices}
                }

        except SQLAlchemyError as e:
            logger.error(f"Database error updating {room_type}: {str(e)}")
            self.event_system.trigger('ERROR', {
                'component': 'FloorPlan',
                'message': f"Failed to update room data: {room_type}",
                'error': str(e)
            })
        except Exception as e:
            logger.error(f"Unexpected error updating {room_type}: {str(e)}")
            raise

    def _handle_mqtt_update(self, msg):
        """Update sensor displays from MQTT messages"""
        try:
            data = json.loads(msg.payload)
            device_id = int(msg.topic.split('/')[2].split('_')[-1])
            status = f"{data['value']} {data.get('unit', '')}".strip()
            self.update_device_status(device_id, status)
        except Exception as e:
            logger.error(f"Error handling MQTT update: {str(e)}") 

    def _setup_event_handlers(self):
        """Set up event handlers for sensor updates"""
        try:
            self.event_system.on('device_update', self._handle_device_update)
            self.event_system.on('sensor_update', self._handle_sensor_update)
            logger.info("Event handlers set up successfully")
        except Exception as e:
            logger.error(f"Error setting up event handlers: {e}")

    async def _handle_device_update(self, data):
        """Handle device update events using data binding"""
        try:
            device_id = data.get('device_id')
            updates = data.get('device_updates', 0)
            device_name = data.get('device_name', '')
            
            logger.debug(f"Received device update: {data}")
            
            if device_id in self.device_states:
                # Update counter state
                self.device_states[device_id]['counter'] = updates
                logger.debug(f"Updated counter state for device {device_id} to {updates}")
                
                # Update UI if element exists
                if device_id in self.device_elements:
                    device_element = self.device_elements[device_id]
                    counter = device_element.get('counter')
                    
                    if counter is not None:
                        try:
                            # Update using set_text for proper UI refresh
                            counter.set_text(str(updates))
                            logger.debug(f"Updated counter UI for device {device_id} to {updates}")
                        except Exception as e:
                            logger.error(f"Error updating counter UI for device {device_id}: {str(e)}")
                            # Try to recreate the counter element if update failed
                            try:
                                await self._recreate_device_counter(device_id, device_name, updates)
                            except Exception as e2:
                                logger.error(f"Failed to recreate counter for device {device_id}: {str(e2)}")
                    else:
                        logger.warning(f"Counter element is None for device {device_id}")
                        # Try to create the counter element
                        try:
                            await self._recreate_device_counter(device_id, device_name, updates)
                        except Exception as e:
                            logger.error(f"Failed to create counter for device {device_id}: {str(e)}")
                else:
                    logger.warning(f"Device {device_id} not found in device_elements")
            else:
                logger.warning(f"Device {device_id} not found in device_states")
                
        except Exception as e:
            logger.error(f"Error handling device update: {e}")
            logger.debug(f"Problematic event data: {json.dumps(data, indent=2)}")

    async def _recreate_device_counter(self, device_id, device_name, counter_value):
        """Recreate a device counter element"""
        try:
            # Find the device's room card
            room_type = None
            for room, devices in self.rooms.items():
                for device in devices:
                    if str(device_id) == str(device.get('id')):
                        room_type = room
                        break
                if room_type:
                    break
            
            if room_type and room_type in self.room_elements:
                room_card = self.room_elements[room_type]
                with room_card['container']:
                    # Create a new counter element
                    counter = ui.label(str(counter_value)).classes('device-counter')
                    
                    # Update device elements dictionary
                    if device_id not in self.device_elements:
                        self.device_elements[device_id] = {}
                    self.device_elements[device_id]['counter'] = counter
                    
                    logger.info(f"Recreated counter element for device {device_name} (ID: {device_id})")
                    return counter
            else:
                logger.error(f"Could not find room card for device {device_id}")
                
        except Exception as e:
            logger.error(f"Error recreating counter element: {e}")
            raise

    async def _handle_sensor_update(self, data):
        """Handle sensor update events using data binding"""
        try:
            sensor_id = data.get('sensor_id')
            new_value = data.get('value')
            unit = data.get('unit', '')
            
            if sensor_id in self.sensor_states:
                # Update the raw value and unit
                self.sensor_states[sensor_id]['value'] = new_value
                self.sensor_states[sensor_id]['unit'] = unit
                
                # Update the display value
                self.sensor_states[sensor_id]['display_value'] = self._format_value_with_unit(new_value, unit)
                
                logger.debug(f"Updated sensor {sensor_id} value to {new_value}{unit}")
                
        except Exception as e:
            logger.error(f"Error handling sensor update: {e}")
            logger.debug(f"Problematic event data: {json.dumps(data, indent=2)}")

    def _create_sensor_display(self, sensor):
        """Create a UI element for sensor display"""
        with ui.element('div').classes('sensor-display'):
            label = ui.label().classes('text-sm')
            self.sensor_displays[sensor.id] = label
        return label 

    async def _add_device(self, room_card: dict, device_data: dict) -> dict:
        """Add new device to room visualization with proper binding"""
        try:
            logger.debug(f"Creating device element for {device_data['name']}")
            with room_card['container']:
                with ui.card().classes("device-card w-full") as device_card:
                    ui.label(device_data['name']).classes("font-bold")
                    sensors_column = ui.column().classes("gap-1")
                    
                    # Create sensor displays
                    sensor_elements = []
                    for sensor in device_data['sensors']:
                        with sensors_column:
                            sensor_element = self._create_sensor_display(sensor)
                            sensor_element.text = f"{sensor['name']}: {sensor.get('value', 'N/A')}{sensor.get('unit', '')}"
                            sensor_elements.append(sensor_element)
            
            # Force UI refresh
            await device_card.update()
            logger.debug(f"Added device {device_data['name']} with {len(sensor_elements)} sensors")
            return {
                'card': device_card,
                'name': device_data['name'],
                'sensors': sensor_elements
            }
            
        except Exception as e:
            logger.error(f"Failed to add device {device_data['name']}: {str(e)}")
            return {}

    def update_device_status(self, device_id: int, status: str):
        if device_id in self.device_labels:
            current_text = self.device_labels[device_id].text
            new_text = f"{current_text.split(':')[0]}: {status}"
            self.device_labels[device_id].set_text(new_text)

    async def _recreate_display(self, sensor_id):
        """Recreate display for sensor"""
        try:
            sensor = self.db().query(Sensor).get(sensor_id)
            if sensor:
                display = self._create_sensor_display(sensor)
                display.text = self._format_sensor_value(sensor)
                self.sensor_displays[sensor_id] = display
                logger.info(f"Recreated display for sensor {sensor_id}")
            else:
                logger.error(f"Failed to recreate display for sensor {sensor_id}: Sensor not found")
        except Exception as e:
            logger.error(f"Failed to recreate display for sensor {sensor_id}: {str(e)}")

    async def _remove_device(self, room_card, device_name):
        """Remove device from room visualization"""
        try:
            for device_element in room_card['devices']:
                if device_element['name'] == device_name:
                    await device_element['card'].delete()
                    room_card['devices'].remove(device_element)
                    logger.info(f"Removed device {device_name} from room card")
                    return
            logger.error(f"Failed to remove device {device_name}: Device not found")
        except Exception as e:
            logger.error(f"Failed to remove device {device_name}: {str(e)}")

    async def _update_device_status(self, device_element, new_status):
        """Update device status in room visualization"""
        try:
            device_element['status'] = new_status
            await device_element['card'].update()
            logger.info(f"Updated device status: {device_element['name']} → {new_status}")
        except Exception as e:
            logger.error(f"Failed to update device status: {str(e)}")

    def _normalize_room_name(self, room_name: str) -> str:
        """Normalize room name for consistent comparison"""
        return room_name.lower().strip().replace(" ", "_")