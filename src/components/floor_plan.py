import json
from loguru import logger
from nicegui import ui
from src.database import SessionLocal
from src.models.room import Room
from src.models.device import Device
from src.models.sensor import Sensor
from src.models.container import Container
from src.utils.event_system import EventSystem
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, List
import asyncio
from sqlalchemy.orm import joinedload
import random
from datetime import datetime
import threading
import time  # Add time module for UI refresh timing
from src.utils.smart_home_simulator import SmartHomeSimulator

class FloorPlan:
    # Class-level task tracking
    _class_ui_refresh_task = None
    _refresh_task_lock = asyncio.Lock()
    
    # Singleton instance tracking
    _instance = None
    
    def __new__(cls, event_system=None):
        """Create singleton instance or return existing instance"""
        if cls._instance is None:
            logger.info("Creating new FloorPlan instance")
            cls._instance = super(FloorPlan, cls).__new__(cls)
            cls._instance._initialized = False
        else:
            logger.info("Returning existing FloorPlan instance")
        return cls._instance
    
    def __init__(self, event_system: EventSystem = None):
        """Initialize FloorPlan component (only runs once)"""
        # Skip initialization if already initialized
        if getattr(self, "_initialized", False):
            logger.debug("FloorPlan already initialized, skipping initialization")
            return
            
        logger.info("Initializing FloorPlan singleton")
        self._initialized = True
        
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
        self.device_control_dialogs = {}  # Store device control dialogs
        self.simulator = SmartHomeSimulator.get_instance(self.event_system)  # Get simulator instance
        self.last_ui_refresh = 0  # Track when we last refreshed the UI
        self.ui_refresh_interval = 5.0  # Increased to 5 seconds to reduce refresh frequency
        
        # Now register the direct event handlers for real-time updates
        self.event_system.on('sensor_update', self._handle_sensor_update_event)
        self.event_system.on('device_update', self._handle_device_update_event)
        
        # Start the UI refresh task (with class-level tracking)
        self._start_ui_refresh_task()
        
        logger.info("FloorPlan singleton initialized with event handlers registered")

    def _normalize_room_type(self, room_type: str) -> str:
        """Normalize room type for consistent comparison"""
        return room_type.lower().replace(' ', '_')
    
    async def _handle_sensor_update_event(self, data):
        """Event handler that calls the public sensor update method"""
        try:
            sensor_id = data.get('sensor_id') or data.get('id')
            device_id = data.get('device_id')
            value = data.get('value')
            unit = data.get('unit', '')
            
            if all([sensor_id, device_id, value is not None]):
                # Also store the data in our sensor states for later reference
                self.sensor_states[sensor_id] = {
                    'value': value,
                    'unit': unit,
                    'device_id': device_id,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Update the UI directly
                await self.update_sensor_value(sensor_id, device_id, value, unit)
        except Exception as e:
            logger.error(f"Error handling sensor update event: {e}")
    
    async def _handle_device_update_event(self, data):
        """Event handler that calls the public device counter update method"""
        try:
            device_id = data.get('device_id')
            update_counter = data.get('update_counter', 0)
            status = data.get('status', None)
            
            if device_id is not None:
                # Store the device state for later reference
                self.device_states[device_id] = {
                    'name': data.get('name', ''),
                    'type': data.get('type', ''),
                    'location': data.get('location', 'Unknown'),
                    'update_counter': update_counter,
                    'status': status
                }
                
                # Update the counter badge
                await self.update_device_counter(device_id, update_counter)
                
                # Also update status if provided
                if status is not None:
                    await self.update_device_status(device_id, status)
        except Exception as e:
            logger.error(f"Error handling device update event: {e}")
            
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
                        'type': device.type,  # Ensure device type is included
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
            device_type = device_data.get('type', '')
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
                        
                        # Name with flex-grow to take available space
                        ui.label(device_name).classes('text-lg font-semibold text-gray-800 flex-grow')
                        
                        # Add update counter bubble
                        counter_bubble = ui.badge('0').classes('min-w-[28px] bg-primary text-white rounded-full')
                        
                        # Add control button if this is a controllable device type
                        if device_type in ['hvac_system', 'thermostat', 'blinds', 'irrigation', 'ac', 'ac_system']:
                            # Create a container for the control button to add the pulse animation
                            with ui.element('div').classes('relative'):
                                # Make the control button more visible and descriptive
                                control_button = ui.button(
                                    'Control', 
                                    icon='settings',
                                    on_click=lambda d_id=device_id: self._show_device_controls(d_id)
                                ).props('no-caps').classes('bg-blue-500 text-white hover:bg-blue-600 z-10')
                                
                                # Add CSS keyframe animation for the pulse effect
                                ui.add_head_html("""
                                <style>
                                @keyframes pulse-animation {
                                    0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
                                    70% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); }
                                    100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
                                }
                                .pulse {
                                    animation: pulse-animation 2s infinite;
                                }
                                </style>
                                """)
                                
                                # Apply the pulse class to the button
                                control_button.classes('pulse')
                                
                                # Add tooltip to explain functionality
                                with control_button:
                                    ui.tooltip(f'Configure {device_name} settings')
                    
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
                                        ui.label(sensor_name).classes('text-sm text-gray-600 flex-grow')
                                        
                                        # Value and unit right-aligned
                                        value_label = ui.label(formatted_value)
                                        value_label.classes('sensor-value text-sm font-medium text-gray-800 tabular-nums text-right')
                                    
                                    # Store sensor display references
                                    sensor_elements[sensor_id] = value_label
                                    self.sensor_displays[sensor_id] = value_label
                                    
                                    logger.debug(f"Created sensor element for {sensor_name} (ID: {sensor_id})")
                    
                    # Store elements - now include the counter bubble reference
                    if device_id not in self.device_elements:
                        self.device_elements[device_id] = {}
                    self.device_elements[device_id].update({
                        'container': container,
                        'sensors': sensor_elements,
                        'counter': counter_bubble,
                        'name': device_name,
                        'type': device_type
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

    async def _handle_device_update(self, data):
        """Handle device update events using data binding"""
        try:
            logger.debug(f"Device update received: {data}")
            device_id = data.get('device_id')
            device_name = data.get('name', '')
            updates = data.get('update_counter', 0)
            
            # Log to debug the data we're getting
            logger.debug(f"Device update received: {device_id}, name: {device_name}, counter: {updates}")
            
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
                
            # Update device counter through the public method
            await self.update_device_counter(device_id, updates)
        except Exception as e:
            logger.error(f"Error in device update handler: {str(e)}")

    async def _handle_sensor_update(self, data):
        """Handle sensor update events using data binding"""
        try:
            # Log more details about the update
            logger.debug(f"Sensor update received: {data}")
            
            # Extract sensor data - handle both direct sensor updates and device updates
            sensor_id = data.get('sensor_id')  # From device update
            if not sensor_id:
                sensor_id = data.get('id')  # From direct sensor update
            sensor_name = data.get('name')
                
            device_id = data.get('device_id')
            new_value = data.get('value')
            unit = data.get('unit', '')
            
            if not all([sensor_id, device_id, new_value is not None]):
                logger.debug(f"Skipping sensor update due to missing data: {data}")
                return
            
            # Update sensor value through the public method
            await self.update_sensor_value(sensor_id, device_id, new_value, unit)
        except Exception as e:
            logger.error(f"Error handling sensor update: {str(e)}")
            logger.debug(f"Problematic event data: {data}")

    async def update_device_counter(self, device_id, update_counter):
        """Public method to update a device's counter badge
        
        Args:
            device_id: The ID of the device to update
            update_counter: The new counter value to display
        """
        try:
            logger.debug(f"Updating counter for device {device_id} to {update_counter}")
            
            # Update the counter badge with the value from the simulator
            if device_id in self.device_elements and 'counter' in self.device_elements[device_id]:
                counter_badge = self.device_elements[device_id]['counter']
                counter_badge.text = str(update_counter)
                # Force immediate update for this element
                ui.update(counter_badge)
                # Record when we last updated the UI
                self.last_ui_refresh = time.time()
                logger.debug(f"Updated counter badge for device {device_id} to {update_counter}")
            else:
                logger.debug(f"No counter badge found for device {device_id}")
        except Exception as e:
            logger.error(f"Error updating device counter: {str(e)}")

    async def update_sensor_value(self, sensor_id, device_id, new_value, unit=''):
        """Public method to update a sensor's value display
        
        Args:
            sensor_id: The ID of the sensor to update
            device_id: The ID of the device that contains the sensor
            new_value: The new sensor value
            unit: The unit of measurement (optional)
        """
        try:
            logger.debug(f"Updating sensor {sensor_id} value to {new_value} {unit}")
            
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
                    
                    # Update the label text directly - avoid batching for real-time responsiveness
                    sensor_label.text = formatted_value
                    
                    # Force immediate update for this element to ensure real-time display
                    ui.update(sensor_label)
                    
                    # Record when we last updated the UI
                    self.last_ui_refresh = time.time()
                    
                    logger.debug(f"Updated sensor {sensor_id} to {formatted_value}")
                except Exception as e:
                    logger.error(f"Error updating sensor label: {str(e)}")
            else:
                if not sensor_label:
                    logger.debug(f"No UI element found for sensor {sensor_id} in device {device_id}")
                if not container:
                    logger.debug(f"No container found for device {device_id}")
        except Exception as e:
            logger.error(f"Error updating sensor value: {str(e)}")

    def update_device_status(self, device_id: int, status: str):
        """Update the status display for a device
        
        Args:
            device_id: The ID of the device to update
            status: The new status string to display
        """
        if device_id in self.device_labels:
            current_text = self.device_labels[device_id].text
            new_text = f"{current_text.split(':')[0]}: {status}"
            self.device_labels[device_id].set_text(new_text)
            logger.debug(f"Updated device {device_id} status to {status}")
        else:
            logger.debug(f"No label found for device {device_id}")

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

    def reset_update_counters(self, device_id=None):
        """Reset update counters for all devices or a specific device"""
        try:
            with SessionLocal() as session:
                if device_id:
                    # Reset counter for a specific device
                    device = session.query(Device).filter_by(id=device_id).first()
                    if device:
                        device.update_count = 0
                        session.commit()
                else:
                    # Reset counters for all devices
                    session.query(Device).update({Device.update_count: 0})
                    session.commit()
            logger.info(f"Reset update counters for {'device ID ' + str(device_id) if device_id else 'all devices'}")
        except Exception as e:
            logger.error(f"Error resetting update counters: {str(e)}")

    def update_container_state(self, container_id=None, is_active=False):
        """Update the UI based on the active state of a container"""
        try:
            logger.info(f"Updating floor plan for container {container_id}, active state: {is_active}")
            
            if container_id is None:
                return
                
            # Get container details from the database
            with SessionLocal() as session:
                container = session.query(Container).filter_by(id=container_id).first()
                
                if not container:
                    logger.warning(f"Container {container_id} not found in database")
                    return
                    
                # Normalize the room type from container name
                container_name_parts = container.name.split(" - ")
                if len(container_name_parts) >= 2:
                    room_type = container_name_parts[1]  # Get room type part
                    normalized_room_type = self._normalize_room_type(room_type)
                    
                    logger.info(f"Updating room {normalized_room_type} for container {container.name}")
                    
                    # Update the room card if it exists
                    if normalized_room_type in self.room_elements:
                        room_card = self.room_elements[normalized_room_type]['container']
                        
                        # Update visual indication of active status
                        if is_active:
                            # Add active indicator
                            room_card.classes('border-2 border-green-500 bg-green-50')
                            logger.info(f"Marked room {normalized_room_type} as active")
                        else:
                            # Remove active indicator
                            room_card.classes('border border-gray-200 bg-white')
                            logger.info(f"Marked room {normalized_room_type} as inactive")
                    else:
                        logger.warning(f"Room {normalized_room_type} not found in UI elements")
                else:
                    logger.warning(f"Could not parse room type from container name: {container.name}")
                
        except Exception as e:
            logger.error(f"Error updating container state: {e}")
            logger.exception("Detailed error trace:")

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

    async def _show_device_controls(self, device_id):
        """Show controls for the selected device"""
        try:
            if device_id not in self.device_elements:
                logger.error(f"Device {device_id} not found in device elements")
                ui.notify(f"Device with ID {device_id} not found", color='negative')
                return
                
            device_data = self.device_elements[device_id]
            device_name = device_data.get('name', 'Unknown Device')
            device_type = device_data.get('type', '')
            
            # Check if dialog already exists
            if hasattr(self, 'device_control_dialogs') and device_id in self.device_control_dialogs and self.device_control_dialogs[device_id].value:
                # Dialog already open, bring to front
                return
                
            # Initialize device_control_dialogs if it doesn't exist
            if not hasattr(self, 'device_control_dialogs'):
                self.device_control_dialogs = {}
                
            # Create control dialog
            with ui.dialog() as dialog:
                self.device_control_dialogs[device_id] = dialog
                
                with ui.card().classes('p-4 w-96'):
                    ui.label(f'Control {device_name}').classes('text-xl font-bold mb-4')
                    
                    # Different controls based on device type
                    if device_type in ['hvac_system', 'ac', 'ac_system']:
                        await self._create_ac_controls(device_id, dialog)
                    elif device_type == 'thermostat':
                        await self._create_thermostat_controls(device_id, dialog)
                    elif device_type == 'blinds':
                        await self._create_blinds_controls(device_id, dialog)
                    elif device_type == 'irrigation':
                        await self._create_irrigation_controls(device_id, dialog)
                    else:
                        ui.label('No controls available for this device type').classes('text-gray-500')
                        
                    # Add close button at the bottom
                    with ui.row().classes('w-full justify-end mt-4'):
                        ui.button('Close', icon='close', on_click=dialog.close).props('flat')
            
            # Ensure the dialog is opened
            dialog.open()
            ui.notify(f"Opening controls for {device_name}", color='info')
            
        except Exception as e:
            logger.error(f"Error showing device controls: {str(e)}")
            ui.notify(f"Error showing device controls: {str(e)}", color='negative')

    async def _create_ac_controls(self, device_id, dialog):
        """Create controls for whole home AC"""
        try:
            # Get current values from sensors
            with SessionLocal() as session:
                device = session.query(Device).filter(Device.id == device_id).options(joinedload(Device.sensors)).first()

                if not device:
                    ui.label('Device not found').classes('text-red-500')
                    return

                # Initialize current values
                sensor_values = {'power': False, 'set_temperature': 22, 'mode': 0, 'fan_speed': 3}

                logger.debug(f"Device found: {device.name}")
                for sensor in device.sensors:
                    logger.debug(f"Sensor found: {sensor.name} (Type: {sensor.type})")
                    if sensor.type in sensor_values:
                        sensor_values[sensor.type] = sensor.current_value or sensor_values[sensor.type]

                logger.debug(f"Current values - Power: {sensor_values['power']}, Temperature: {sensor_values['set_temperature']}, Mode: {sensor_values['mode']}, Fan Speed: {sensor_values['fan_speed']}")

                # Create UI components
                power_switch = ui.switch('Power', value=sensor_values['power']).classes('mb-4')
                temp_slider = ui.slider(min=16, max=30, step=0.5, value=sensor_values['set_temperature']).classes('mb-2')
                temp_label = ui.label(f'Temperature: {sensor_values["set_temperature"]}°C').classes('text-sm mb-4')

                mode_options = {0: 'Auto', 1: 'Cool', 2: 'Heat', 3: 'Fan', 4: 'Dry'}
                fan_speed_options = {1: 'Low', 2: 'Medium', 3: 'High', 4: 'Very High', 5: 'Max'}

                mode_select = ui.select(options=mode_options, label='Select AC Mode').props('outlined options-dense').classes('min-w-[200px]')
                fan_speed_select = ui.select(options=fan_speed_options, label='Select Fan Speed').props('outlined options-dense').classes('min-w-[200px]')

                mode_select.on('update:model-value', lambda e: logger.debug(f'Mode changed to: {e}'))
                fan_speed_select.on('update:model-value', lambda e: logger.debug(f'Fan speed changed to: {e}'))

                # Update temperature label when slider changes
                temp_slider.on('update:model-value', lambda e: temp_label.set_text(f'Temperature: {float(e.args):.1f}°C'))

                # Apply button and status label
                apply_button = ui.button('Apply Settings', icon='save').classes('mt-2')
                status_label = ui.label('').classes('text-sm mt-2')

                # Apply settings function
                def apply_settings():
                    status_label.text = 'Applying AC settings...'
                    status_label.classes('text-blue-500')

                    try:
                        temp = float(temp_slider.value)
                        mode = mode_select.value
                        fan = fan_speed_select.value

                        logger.info(f"Applying AC settings - Power: {power_switch.value}, Temp: {temp}, Mode: {mode}, Fan: {fan}")

                        success = self.simulator.set_ac_parameters(
                            power=power_switch.value,
                            temperature=temp,
                            mode=mode,
                            fan_speed=fan
                        )

                        if success:
                            status_label.text = 'Settings applied successfully!'
                            status_label.classes('text-green-500')
                            ui.notify('AC settings updated successfully', color='positive')
                            ui.timer(1.5, dialog.close, once=True)
                        else:
                            status_label.text = 'Failed to apply settings!'
                            status_label.classes('text-red-500')
                            ui.notify('Failed to update AC settings', color='negative')
                    except Exception as e:
                        logger.error(f"Error applying AC settings: {e}")
                        status_label.text = f'Error: {str(e)}'
                        status_label.classes('text-red-500')
                        ui.notify(f'Error: {str(e)}', color='negative')

                apply_button.on('click', apply_settings)
        except Exception as e:
            logger.error(f"Error creating AC controls: {e}")
            ui.label(f'Error creating controls: {str(e)}').classes('text-red-500')

    async def _create_thermostat_controls(self, device_id, dialog):
        """Create controls for room thermostat"""
        try:
            # Get current values from sensors
            with SessionLocal() as session:
                device = session.query(Device).filter(Device.id == device_id).options(joinedload(Device.sensors)).first()

                if not device:
                    ui.label('Device not found').classes('text-red-500')
                    return

                # Initialize current values
                power_value = False
                temp_value = 22
                mode_value = 0

                # Retrieve sensor values
                for sensor in device.sensors:
                    if sensor.type == 'power':
                        power_value = sensor.current_value == 1
                    elif sensor.type == 'set_temperature':
                        temp_value = sensor.current_value or 22
                    elif sensor.type == 'mode':
                        mode_value = int(sensor.current_value or 0)

            # Create power switch
            power_switch = ui.switch('Power', value=power_value).classes('mb-4')

            # Position slider
            temp_slider = ui.slider(min=16, max=30, step=0.5, value=temp_value).classes('mb-2')
            temp_label = ui.label(f'Temperature: {temp_value}°C').classes('text-sm mb-4')

            # Mode selection
            mode_options = {0: 'Auto', 1: 'Cool', 2: 'Heat', 3: 'Fan'}  # Mode must be 0 (Auto), 1 (Cool), 2 (Heat), or 3 (Fan)

            mode_select = ui.select(
                options=mode_options,
                label='Thermostat Mode'
            ).props('outlined options-dense')
            mode_select.classes('min-w-[200px]')
            mode_select.on('update:model-value', lambda e: logger.debug(f'Mode changed to: {e}'))

            # Update temperature label when slider changes
            def update_temp_label(e):
                try:
                    temp_value = float(e.args)  # Directly use e.args as it contains the temperature value
                    temp_label.text = f'Temperature: {temp_value:.1f}°C'  # Update the label with the correct value
                except (ValueError, TypeError) as error:
                    logger.error(f'Error updating temperature label: {error}')
                    temp_label.text = 'Temperature: Error'  # Fallback text in case of error

            temp_slider.on('update:model-value', update_temp_label)

            # Apply button
            apply_button = ui.button('Apply Settings', icon='save').classes('mt-2')
            status_label = ui.label('').classes('text-sm mt-2')

            # Apply settings function
            def apply_settings():
                logger.debug(f'Applying thermostat settings - Power: {power_switch.value}, Temp: {temp_slider.value}, Mode: {mode_select.value}')
                status_label.text = 'Applying settings...'
                status_label.classes('text-blue-500')

                try:
                    success = self.simulator.set_thermostat(
                        room_id=device.room_id,
                        power=power_switch.value,
                        temperature=temp_slider.value,
                        mode=mode_select.value
                    )

                    if success:
                        status_label.text = 'Settings applied successfully!'
                        status_label.classes('text-green-500')
                        # Close dialog after short delay
                        ui.timer(1.5, dialog.close, once=True)
                    else:
                        status_label.text = 'Failed to apply settings!'
                        status_label.classes('text-red-500')
                except Exception as e:
                    logger.error(f"Error applying thermostat settings: {e}")
                    status_label.text = f'Error: {str(e)}'
                    status_label.classes('text-red-500')

            apply_button.on('click', apply_settings)
        except Exception as e:
            logger.error(f"Error creating thermostat controls: {e}")
            ui.label(f'Error creating controls: {str(e)}').classes('text-red-500')

    async def _create_blinds_controls(self, device_id, dialog):
        """Create controls for smart blinds"""
        try:
            # Get current values from sensors
            with SessionLocal() as session:
                device = session.query(Device).filter(Device.id == device_id).options(joinedload(Device.sensors)).first()

                if not device:
                    ui.label('Device not found').classes('text-red-500')
                    return

                # Find current values
                position_value = 50
                mode_value = 0

                for sensor in device.sensors:
                    if sensor.type == 'position':
                        position_value = sensor.current_value or 50
                    elif sensor.type == 'mode':
                        mode_value = int(sensor.current_value or 0)

            # Position slider
            position_slider = ui.slider(min=0, max=100, step=1, value=position_value).classes('mb-2')
            position_label = ui.label(f'Position: {position_value}%').classes('text-sm mb-4')

            # Mode selection
            mode_options = {0: 'Manual', 1: 'Auto', 2: 'Scheduled'}  # Mode must be 0 (Manual), 1 (Auto), or 2 (Scheduled)

            mode_select = ui.select(
                options=mode_options,
                label='Mode'
            ).props('outlined options-dense')
            mode_select.classes('min-w-[200px]')
            mode_select.on('update:model-value', lambda e: logger.debug(f'Mode changed to: {e}'))

            # Update position label when slider changes
            def update_position_label(e):
                try:
                    position_value = float(e.args)  # Directly use e.args as it contains the position value
                    position_label.text = f'Position: {position_value}%'  # Update the label with the correct value
                except (ValueError, TypeError) as error:
                    logger.error(f'Error updating position label: {error}')
                    position_label.text = 'Position: Error'  # Fallback text in case of error

            position_slider.on('update:model-value', update_position_label)

            # Apply button
            apply_button = ui.button('Apply Settings', icon='save').classes('mt-2')
            status_label = ui.label('').classes('text-sm mt-2')

            # Apply settings function
            def apply_settings():
                status_label.text = 'Applying settings...'
                status_label.classes('text-blue-500')

                try:
                    success = self.simulator.set_blinds(
                        room_id=device.room_id,
                        position=position_slider.value,
                        mode=mode_select.value
                    )

                    if success:
                        status_label.text = 'Settings applied successfully!'
                        status_label.classes('text-green-500')
                        # Close dialog after short delay
                        ui.timer(1.5, dialog.close, once=True)
                    else:
                        status_label.text = 'Failed to apply settings!'
                        status_label.classes('text-red-500')
                except Exception as e:
                    logger.error(f"Error applying blinds settings: {e}")
                    status_label.text = f'Error: {str(e)}'
                    status_label.classes('text-red-500')

            apply_button.on('click', apply_settings)
        except Exception as e:
            logger.error(f"Error creating blinds controls: {e}")
            ui.label(f'Error creating controls: {str(e)}').classes('text-red-500')

    async def _create_irrigation_controls(self, device_id, dialog):
        """Create controls for smart irrigation system"""
        try:
            # Get current values from sensors
            with SessionLocal() as session:
                device = session.query(Device).filter(Device.id == device_id).options(joinedload(Device.sensors)).first()

                if not device:
                    ui.label('Device not found').classes('text-red-500')
                    return

                # Find current values
                moisture_value = 0
                flow_value = 0
                schedule_value = 0

                for sensor in device.sensors:
                    if sensor.type == 'moisture':
                        moisture_value = sensor.current_value or 0
                    elif sensor.type == 'flow':
                        flow_value = sensor.current_value or 0
                    elif sensor.type == 'schedule':
                        schedule_value = sensor.current_value or 0

            # Display current readings
            ui.label(f'Current Soil Moisture: {moisture_value}%').classes('text-sm mb-2')
            ui.label(f'Current Water Flow: {flow_value} L/min').classes('text-sm mb-4')

            # Schedule toggle
            schedule_switch = ui.switch('Automatic Watering Schedule', value=schedule_value == 1).classes('mb-4')

            # Water now button
            water_button = ui.button('Water Now (5 minutes)', icon='water_drop').classes('mb-2')

            # Apply button
            apply_button = ui.button('Save Schedule Setting', icon='save').classes('mt-2')
            status_label = ui.label('').classes('text-sm mt-2')

            # Apply settings function
            def apply_settings():
                logger.debug(f'Applying irrigation settings - Schedule: {schedule_switch.value}')
                status_label.text = 'Applying settings...'
                status_label.classes('text-blue-500')

                try:
                    # Update schedule sensor
                    with SessionLocal() as session:
                        schedule_sensor = session.query(Sensor).filter(
                            Sensor.device_id == device_id,
                            Sensor.type == 'schedule'
                        ).first()

                        if schedule_sensor:
                            schedule_sensor.current_value = 1 if schedule_switch.value else 0
                            session.commit()

                            status_label.text = 'Settings applied successfully!'
                            status_label.classes('text-green-500')
                            # Close dialog after short delay
                            ui.timer(1.5, dialog.close, once=True)
                        else:
                            status_label.text = 'Schedule sensor not found!'
                            status_label.classes('text-red-500')
                except Exception as e:
                    logger.error(f"Error applying irrigation settings: {e}")
                    status_label.text = f'Error: {str(e)}'
                    status_label.classes('text-red-500')

            # Water now function
            def water_now():
                status_label.text = 'Starting irrigation...'
                status_label.classes('text-blue-500')

                try:
                    # Update flow sensor to simulate watering
                    with SessionLocal() as session:
                        flow_sensor = session.query(Sensor).filter(
                            Sensor.device_id == device_id,
                            Sensor.type == 'flow'
                        ).first()

                        if flow_sensor:
                            flow_sensor.current_value = 5.0  # 5 L/min flow rate
                            session.commit()

                            # Trigger sensor update event
                            asyncio.create_task(self.event_system.emit('sensor_update', {
                                'id': flow_sensor.id,
                                'device_id': device_id,
                                'name': flow_sensor.name,
                                'value': flow_sensor.current_value,
                                'unit': flow_sensor.unit
                            }))

                            status_label.text = 'Irrigation started for 5 minutes'
                            status_label.classes('text-green-500')

                            # Schedule stop after 5 minutes (just for UI feedback)
                            ui.timer(5, lambda: status_label.set_text('Irrigation completed'), once=True)
                        else:
                            status_label.text = 'Flow sensor not found!'
                            status_label.classes('text-red-500')
                except Exception as e:
                    logger.error(f"Error starting irrigation: {e}")
                    status_label.text = f'Error: {str(e)}'
                    status_label.classes('text-red-500')

            apply_button.on('click', apply_settings)
            water_button.on('click', water_now)
        except Exception as e:
            logger.error(f"Error creating irrigation controls: {e}")
            ui.label(f'Error creating controls: {str(e)}').classes('text-red-500')

    def _start_ui_refresh_task(self):
        """Start a task to periodically refresh the UI to ensure it's always up-to-date"""
        async def ui_refresh_loop():
            instance_id = id(self)
            logger.debug(f"FloorPlan[{instance_id}]: UI refresh loop started")
            while True:
                try:
                    # Sleep at the beginning to prevent immediate and frequent refreshes
                    await asyncio.sleep(self.ui_refresh_interval)
                    # Only do a refresh if we haven't updated recently
                    current_time = time.time()
                    if (current_time - self.last_ui_refresh) >= self.ui_refresh_interval:
                        self.last_ui_refresh = current_time
                        # Just call ui.update() to refresh the entire UI
                        ui.update()
                        logger.debug(f"FloorPlan[{instance_id}]: Performed periodic UI refresh")
                except Exception as e:
                    logger.error(f"FloorPlan[{instance_id}]: Error in UI refresh loop: {e}")
                    await asyncio.sleep(5.0)  # Wait longer if there was an error
        
        async def start_refresh_task():
            # Acquire the lock to ensure thread-safe creation/cancellation of tasks
            async with FloorPlan._refresh_task_lock:
                # Cancel existing class-level task if it exists
                if FloorPlan._class_ui_refresh_task is not None:
                    logger.info(f"FloorPlan[{id(self)}]: Cancelling existing UI refresh task")
                    FloorPlan._class_ui_refresh_task.cancel()
                    try:
                        # Wait for task to be properly cancelled
                        await asyncio.sleep(0.1)
                    except:
                        pass
                
                # Create a new refresh task
                FloorPlan._class_ui_refresh_task = asyncio.create_task(ui_refresh_loop())
                logger.info(f"FloorPlan[{id(self)}]: Started new periodic UI refresh task")
        
        # Schedule the task creation
        asyncio.create_task(start_refresh_task())