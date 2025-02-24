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
        self.rooms = {}
        self.device_states = {}
        self.sensor_states = {}
        self.device_room_map = {}  # New mapping to track device-room relationships
        self.sensor_displays = {}
        self.room_labels = {}
        self.device_labels = {}
        self.device_elements = {}
        self.update_lock = asyncio.Lock()
        self.pending_updates = {}  # Track sensors that need UI updates
        self._setup_event_handlers()
        
        # Start the update processing task
        ui.timer(0.1, self._process_updates, active=True)

    def _normalize_room_type(self, room_type: str) -> str:
        """Normalize room type for consistent comparison"""
        return room_type.lower().strip().replace(" ", "_")

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
        icon_map = {
            # Environmental sensors
            'temperature': 'thermostat',
            'humidity': 'water_drop',
            'air_quality': 'air',
            'co2': 'co2',
            'pressure': 'speed',
            'light': 'light_mode',
            'brightness': 'brightness_high',
            'color_temp': 'wb_sunny',
            'uv': 'wb_sunny',
            
            # Security sensors
            'motion': 'motion_sensor',
            'door': 'door_front',
            'window': 'window',
            'contact_sensor': 'sensor_door',
            'presence': 'person_search',
            'occupancy': 'person',
            'camera': 'videocam',
            
            # Safety sensors
            'smoke': 'detector_smoke',
            'co': 'detector_alarm',
            'gas': 'gas_meter',
            'water_leak': 'water_damage',
            'flood': 'water_damage',
            
            # Power/Energy sensors
            'power': 'power',
            'energy': 'bolt',
            'voltage': 'electric_bolt',
            'current': 'electric_meter',
            'battery': 'battery_full',
            
            # Status indicators
            'status': 'info',
            'state': 'toggle_on',
            'mode': 'tune',
            'scene': 'view_agenda',
            
            # Default icon for unknown types
            'default': 'sensors'
        }
        
        # Normalize sensor type and get appropriate icon
        normalized_type = sensor_type.lower().strip()
        return icon_map.get(normalized_type, icon_map['default'])

    def initialize_floor_plan(self, container=None):
        """Initialize the floor plan visualization with rooms and devices"""
        try:
            with SessionLocal() as session:
                # Load all rooms with devices and sensors
                rooms = session.query(Room).options(
                    joinedload(Room.devices).joinedload(Device.sensors)
                ).all()
                
                # Create room elements first
                for room in rooms:
                    self._create_room_card(room, container)
                    # Store room data for reference with normalized room type
                    normalized_room_type = self._normalize_room_type(room.room_type)
                    self.rooms[normalized_room_type] = room
                
                # Initialize devices and sensors after all rooms are created
                for room in rooms:
                    normalized_room_type = self._normalize_room_type(room.room_type)
                    self._initialize_room_devices(normalized_room_type, room.devices, session)
                
                logger.info(f'Initialized {len(self.rooms)} rooms with devices')
                
        except Exception as e:
            logger.error(f"Error initializing floor plan: {e}")
            raise

    def _create_room_card(self, room, container=None):
        """Create a room card with a container for devices"""
        try:
            grid_container = container or ui.grid(columns=3).classes("gap-4 room-card-container")
            
            with grid_container:
                with ui.card().classes('room-card p-6 shadow-lg hover:shadow-xl transition-shadow duration-200 bg-white') as room_container:
                    # Room header with improved styling
                    with ui.row().classes('w-full items-center gap-4 mb-6 border-b border-gray-100 pb-4'):
                        with ui.row().classes('min-w-[32px] justify-center'):
                            ui.icon('room').classes('text-primary text-2xl')
                        ui.label(f"{room.name}").classes('text-xl font-bold text-gray-800 truncate')
                    
                    # Create devices section with better spacing
                    with ui.column().classes('w-full gap-6') as devices_container:
                        pass  # Devices will be added later
                    
                    # Store room elements using normalized room type
                    normalized_room_type = self._normalize_room_type(room.room_type)
                    self.room_elements[normalized_room_type] = {
                        'container': room_container,
                        'devices_container': devices_container,
                        'devices': []
                    }
                    
                    logger.debug(f"Created room card for {room.room_type} (normalized: {normalized_room_type})")
                
        except Exception as e:
            logger.error(f"Error creating room card for {room.room_type}: {e}")

    def _initialize_room_devices(self, room_type: str, devices: List[Device], session):
        """Initialize devices for a room with proper sensor binding"""
        try:
            normalized_room_type = self._normalize_room_type(room_type)
            if normalized_room_type not in self.room_elements:
                logger.error(f"Room {room_type} (normalized: {normalized_room_type}) not found in room elements")
                return
                
            room_card = self.room_elements[normalized_room_type]
            
            for device in devices:
                try:
                    # Refresh device to ensure sensors are loaded
                    session.refresh(device)
                    
                    # Create device data structure with all sensors
                    device_data = {
                        'id': device.id,
                        'name': device.name,
                        'sensors': []
                    }
                    
                    # Add all sensors
                    for sensor in device.sensors:
                        sensor_data = {
                            'id': sensor.id,
                            'name': sensor.name,
                            'value': sensor.current_value,
                            'unit': sensor.unit,
                            'type': sensor.type
                        }
                        device_data['sensors'].append(sensor_data)
                        logger.debug(f"Added sensor {sensor.name} (ID: {sensor.id}) to device {device.name}")
                    
                    # Add device to room
                    self._add_device(room_card, device_data)
                    
                    # Store room mapping using normalized room type
                    self.device_room_map[device.id] = normalized_room_type
                    
                    logger.debug(f"Initialized device {device.name} with {len(device_data['sensors'])} sensors in {room_type}")
                    
                except Exception as e:
                    logger.error(f"Error initializing device {device.name}: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Error initializing room devices: {e}")

    def _add_device(self, room_card: dict, device_data: dict):
        """Add new device to room visualization with proper binding"""
        try:
            device_id = device_data.get('id')
            device_name = device_data.get('name', '')
            container = room_card.get('container')
            
            if not container:
                logger.error(f"No container found in room card")
                return
                
            with container:
                # Create device card with improved styling
                with ui.card().classes('device-card w-full p-4 shadow-md hover:shadow-lg transition-shadow duration-200'):
                    # Device header with improved alignment
                    with ui.row().classes('w-full items-center justify-start gap-3 mb-3 pb-2 border-b border-gray-100'):
                        ui.icon('device_hub').classes('text-primary text-xl min-w-[28px]')
                        ui.label(device_name).classes('text-lg font-semibold text-gray-800 truncate')
                    
                    # Create sensors container with better spacing
                    sensors_container = ui.column().classes('w-full gap-2 mt-3')
                    
                    # Create sensor displays with improved layout
                    sensor_elements = {}
                    for sensor in device_data.get('sensors', []):
                        with sensors_container:
                            sensor_id = sensor.get('id')
                            if sensor_id:
                                # Initialize with current value if available
                                value = sensor.get('value', 'N/A')
                                if isinstance(value, (int, float)):
                                    value = f"{value:.2f}"
                                
                                # Get sensor type and icon
                                sensor_type = sensor.get('type', '').lower()
                                icon = self.get_sensor_icon(sensor_type)
                                
                                # Format the sensor name and value
                                sensor_name = sensor.get('name', '')
                                unit = sensor.get('unit', '')
                                formatted_value = f"{value} {unit}".strip()
                                
                                # Create sensor row with improved alignment and spacing
                                with ui.card().classes('w-full bg-gray-50/50 hover:bg-gray-100/50 transition-colors duration-200'):
                                    with ui.row().classes('w-full items-center px-3 py-2 gap-3'):
                                        # Icon on the left
                                        ui.icon(icon).classes('text-primary text-xl min-w-[24px]')
                                        
                                        # Name with flex-grow to take available space
                                        ui.label(sensor_name).classes('text-sm text-gray-600 flex-grow truncate')
                                        
                                        # Value and unit right-aligned
                                        value_label = ui.label(formatted_value)
                                        value_label.classes('sensor-value text-sm font-medium text-gray-800 tabular-nums text-right')
                                    
                                    # Store sensor display references
                                    sensor_elements[sensor_id] = value_label
                                    self.sensor_displays[sensor_id] = value_label
                                    
                                    logger.debug(f"Created sensor element for {sensor_name} (ID: {sensor_id})")
                    
                    # Store elements - removing the counter but keeping the dictionary structure
                    if device_id not in self.device_elements:
                        self.device_elements[device_id] = {}
                    self.device_elements[device_id].update({
                        'container': container,
                        'sensors': sensor_elements
                    })
                    
                    logger.debug(f"Added device {device_name} with {len(sensor_elements)} sensors")
                    
        except Exception as e:
            logger.error(f"Error adding device to visualization: {e}")

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
            # First remove any existing handlers
            self.event_system.remove_all_handlers('device_update')
            self.event_system.remove_all_handlers('sensor_update')
            
            # Register our handlers
            self.event_system.on('device_update', self._handle_device_update)
            self.event_system.on('sensor_update', self._handle_sensor_update)
            logger.info("Event handlers set up successfully")
        except Exception as e:
            logger.error(f"Error setting up event handlers: {e}")

    async def _handle_device_update(self, data):
        """Handle device update events using data binding"""
        try:
            device_id = data.get('device_id')
            device_name = data.get('device_name', '')
            updates = data.get('device_updates', 0)
            
            logger.debug(f"Handling device update for {device_name} (ID: {device_id})")
            
            # Get room type from our mapping or database
            room_type = self.device_room_map.get(device_id)
            if not room_type:
                with SessionLocal() as session:
                    device = session.query(Device).get(device_id)
                    if device and device.container:
                        room_type = device.container.location
                        self.device_room_map[device_id] = room_type
            
            if not room_type:
                logger.error(f"Could not find room type for device {device_id}")
                return
                
            # Ensure room exists in our elements
            if room_type not in self.room_elements:
                logger.error(f"Room {room_type} not found in room elements")
                return
                
            # No need to update the counter element as it has been removed
            logger.debug(f"Device update processed for {device_name} (ID: {device_id}, updates: {updates})")
                
        except Exception as e:
            logger.error(f"Error in device update handler: {str(e)}")

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

    async def _batch_update(self):
        """Process all pending updates at once"""
        try:
            if not self.pending_updates:
                return
                
            logger.debug(f"Processing batch update for {len(self.pending_updates)} sensors")
            self.pending_updates.clear()
            
            # Trigger a global UI refresh
            ui.update()
            
        except Exception as e:
            logger.error(f"Error in batch update: {str(e)}")

    async def _handle_sensor_update(self, data):
        """Handle sensor update events using data binding"""
        try:
            # Extract sensor data - handle both direct sensor updates and device updates
            sensor_id = data.get('sensor_id')  # From device update
            if not sensor_id:
                sensor_id = data.get('id')  # From direct sensor update
                
            device_id = data.get('device_id')
            sensor_name = data.get('sensor_name', '') or data.get('name', '')
            new_value = data.get('value')
            unit = data.get('unit', '')
            
            if not all([sensor_id, device_id, new_value is not None]):
                logger.debug(f"Skipping sensor update due to missing data: {data}")
                return
                
            # Find the sensor element and its container
            device_elements = self.device_elements.get(device_id, {})
            sensor_elements = device_elements.get('sensors', {})
            sensor_label = sensor_elements.get(sensor_id)
            container = device_elements.get('container')
            
            if sensor_label and container:
                try:
                    # Format the value nicely
                    formatted_value = f"{new_value:.2f}" if isinstance(new_value, (int, float)) else str(new_value)
                    formatted_value = f"{formatted_value} {unit}".strip()
                    
                    # Store the update data
                    self.pending_updates[sensor_id] = {
                        'label': sensor_label,
                        'container': container,
                        'value': formatted_value,
                        'unit': unit
                    }
                    
                except Exception as e:
                    logger.error(f"Error queueing sensor update: {str(e)}")
            else:
                if not sensor_label:
                    logger.debug(f"No UI element found for sensor {sensor_id} in device {device_id}")
                if not container:
                    logger.debug(f"No container found for device {device_id}")
                
            # Can safely update the label text since we have the reference
            if sensor_label:
                sensor_label.text = formatted_value
                
        except Exception as e:
            logger.error(f"Error handling sensor update: {str(e)}")
            logger.debug(f"Problematic event data: {data}")

    def _process_updates(self):
        """Process all pending sensor updates"""
        try:
            if not self.pending_updates:
                return
                
            # Create a concise batch update summary
            updates = [f"{sid}:{data['value']}{data['unit']}" for sid, data in self.pending_updates.items()]
            if updates:
                logger.debug(f"Batch updates: {', '.join(updates)}")
            
            # Process each update
            for sensor_id, update_data in self.pending_updates.items():
                try:
                    label = update_data['label']
                    text = update_data['value']
                    label.text = text
                except Exception as e:
                    logger.error(f"Error updating sensor {sensor_id}: {str(e)}")
            
            # Clear pending updates after processing
            self.pending_updates.clear()
            
        except Exception as e:
            logger.error(f"Error in update processing: {str(e)}")
            self.pending_updates.clear()

    def create_floor_plan(self, container=None):
        """Generate floor plan visualization with data binding"""
        try:
            grid_container = container or ui.grid(columns=3).classes("gap-4 room-card-container")
            
            with grid_container:
                # Clear existing elements
                self.room_elements.clear()
                self.sensor_displays.clear()
                self.device_elements.clear()
                
                # Initialize the floor plan with the grid container
                self.initialize_floor_plan(grid_container)
                
            logger.info(f"Created floor plan with {len(self.rooms)} rooms")
            
        except Exception as e:
            logger.error(f"Error creating floor plan: {e}")
            raise