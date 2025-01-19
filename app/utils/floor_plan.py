from nicegui import ui
from typing import Dict, List
from datetime import datetime
from constants.device_templates import ROOM_TYPES
from loguru import logger

class FloorPlan:
    """Class to handle floor plan visualization and room updates"""
    
    def __init__(self):
        self.rooms = {room_type: {} for room_type in ROOM_TYPES}
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
                                    # Sensor name and values in a single row
                                    with ui.row().classes('gap-4 items-center flex-grow'):
                                        ui.label(f"{sensor['name']}:").classes('font-bold min-w-[120px]')
                                        # Base value with icon
                                        with ui.row().classes('items-center gap-1'):
                                            ui.icon('radio_button_unchecked', size='16px').classes('text-gray-600')
                                            ui.label(f"{sensor['base_value']:.1f}").classes('text-gray-600')
                                        # Current value with icon
                                        with ui.row().classes('items-center gap-1'):
                                            ui.icon('radio_button_checked', size='16px').classes('text-primary')
                                            ui.label(f"{sensor['current_value']:.1f}").classes('text-primary font-bold')
                                    # Unit display
                                    ui.label(self._get_unit_display(sensor['unit'])).classes('text-gray-500 min-w-[30px] text-right')
        logger.debug(f"Room data update completed for {room_type}")

    def _get_unit_display(self, unit_code: int) -> str:
        """Get the display string for a unit code"""
        unit_map = {
            0: '°C',  # Temperature
            1: '%',   # Humidity
            2: 'lux', # Light level
            3: 'ppm', # Air quality
            4: '%',   # Brightness
            5: '',    # Status (0-1)
            6: 'dB',  # Sound level
            7: 'ppm', # CO2
            8: '%',   # Motion
        }
        unit = unit_map.get(unit_code, '')
        logger.debug(f"Retrieved unit display '{unit}' for unit code {unit_code}")
        return unit
    
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