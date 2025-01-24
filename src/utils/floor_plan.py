from nicegui import ui
from typing import Dict, List
from datetime import datetime
from src.constants.device_templates import ROOM_TYPES
from loguru import logger

class FloorPlan:
    """Class to handle floor plan visualization and room updates"""
    
    def __init__(self):
        self.rooms = {}
        self.sensor_values = {}  # Store sensor values
        for room_type in ROOM_TYPES:
            self.rooms[room_type] = {
                'ui_initialized': False,
                'device_container': None
            }
        self.main_container = None
        logger.debug("Initialized FloorPlan utility component")
        
    def create_floor_plan(self):
        """Create the floor plan visualization"""
        logger.info("Creating floor plan visualization")
        self.main_container = ui.card().classes('w-full')
        with self.main_container:
            ui.label('Floor Plan').classes('text-h6 mb-4')
            
            # Create grid of room cards
            with ui.grid(columns=2).classes('w-full gap-4'):
                for room_type in ROOM_TYPES:
                    self._create_room_card(room_type)
        logger.debug("Floor plan visualization created successfully")
    
    def _create_room_card(self, room_type: str):
        """Create a card for a room"""
        logger.debug(f"Creating room card for {room_type}")
        with ui.card().classes('w-full'):
            ui.label(room_type).classes('text-h6')
            
            # Container for device status
            self.rooms[room_type]['device_container'] = ui.column().classes('w-full mt-2')
            
            # Container for alerts
            self.rooms[room_type]['alert_container'] = ui.column().classes('w-full mt-2')
        logger.debug(f"Room card created for {room_type}")
    
    def update_sensor_value(self, room_type: str, device_name: str, sensor_name: str, current_value: float):
        """Update a specific sensor's value"""
        sensor_key = f"{room_type}_{device_name}_{sensor_name}"
        if sensor_key in self.sensor_values:
            self.sensor_values[sensor_key]['value_label'].text = f"{current_value:.1f}"
            
    def update_room_data(self, room_type: str, devices: list):
        """Update the room data with new device information"""
        if room_type not in self.rooms:
            logger.warning(f"Attempted to update non-existent room: {room_type}")
            return
            
        logger.info(f"Updating room data for {room_type} with {len(devices)} devices")
        device_container = self.rooms[room_type]['device_container']
        if not device_container:
            logger.warning(f"Device container not found for room {room_type}")
            return
            
        # Only clear and rebuild if values have changed
        current_hash = self._get_values_hash(devices)
        if hasattr(self, f'last_hash_{room_type}') and getattr(self, f'last_hash_{room_type}') == current_hash:
            # Just update the values without rebuilding UI
            for device in devices:
                for sensor in device['sensors']:
                    self.update_sensor_value(
                        room_type, 
                        device['name'], 
                        sensor['name'], 
                        sensor['current_value']
                    )
            return
            
        setattr(self, f'last_hash_{room_type}', current_hash)
        device_container.clear()
        
        # Create expandable sections for each device
        with device_container:
            for device in devices:
                logger.debug(f"Adding device {device['name']} to {room_type}")
                with ui.expansion(device['name'], value=True).classes('w-full'):
                    with ui.column().classes('w-full gap-1'):
                        # Display each sensor's data
                        for sensor in device['sensors']:
                            logger.debug(f"Adding sensor {sensor['name']} to device {device['name']}")
                            
                            with ui.card().classes('w-full p-1 bg-gray-50'):
                                with ui.row().classes('w-full justify-between items-center'):
                                    # Left side: sensor name and icon
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon(self._get_sensor_icon(sensor['name'])).classes('text-primary')
                                        ui.label(f"{sensor['name']}:").classes('font-bold')
                                    
                                    # Right side: current value and unit
                                    with ui.row().classes('items-center gap-2'):
                                        # Create labels for values
                                        value_label = ui.label(f"{sensor['current_value']:.1f}").classes('text-lg font-bold text-primary')
                                        unit_label = ui.label(f"{sensor['unit']}").classes('text-sm text-gray-600')
                                        base_label = ui.label(f"(Base: {sensor['base_value']:.1f})").classes('text-xs text-gray-500')
                                        
                                        # Store references to labels
                                        sensor_key = f"{room_type}_{device['name']}_{sensor['name']}"
                                        self.sensor_values[sensor_key] = {
                                            'value_label': value_label,
                                            'unit_label': unit_label,
                                            'base_label': base_label
                                        }

    def _get_values_hash(self, devices: list) -> str:
        """Create a hash of current values to detect changes"""
        values = []
        for device in devices:
            for sensor in device['sensors']:
                values.append(f"{sensor['name']}:{sensor['current_value']}")
        return "|".join(values)

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
        icon = icons.get(sensor_name, 'sensors')
        logger.debug(f"Retrieved icon '{icon}' for sensor {sensor_name}")
        return icon
    
    def add_alert(self, room_type: str, message: str, severity: str = 'warning'):
        """Add an alert to a room"""
        if room_type not in self.rooms:
            logger.warning(f"Attempted to add alert to non-existent room: {room_type}")
            return
            
        logger.info(f"Adding {severity} alert to room {room_type}: {message}")
        alert_container = self.rooms[room_type]['alert_container']
        if not alert_container:
            logger.warning(f"Alert container not found for room {room_type}")
            return
            
        with alert_container:
            with ui.card().classes(f'w-full bg-{severity}-100 q-pa-sm q-mb-sm'):
                ui.label(message).classes(f'text-{severity}')
                ui.label(f"Time: {datetime.now().strftime('%H:%M:%S')}").classes('text-sm')
        logger.debug(f"Alert added to room {room_type}")
    
    def clear_alerts(self, room_type: str = None):
        """Clear alerts for a room or all rooms"""
        if room_type:
            logger.info(f"Clearing alerts for room {room_type}")
            if room_type in self.rooms and self.rooms[room_type]['alert_container']:
                self.rooms[room_type]['alert_container'].clear()
                logger.debug(f"Cleared alert container for room {room_type}")
        else:
            logger.info("Clearing alerts for all rooms")
            for room_name, room in self.rooms.items():
                if 'alert_container' in room and room['alert_container']:
                    room['alert_container'].clear()
                    logger.debug(f"Cleared alert container for room {room_name}") 