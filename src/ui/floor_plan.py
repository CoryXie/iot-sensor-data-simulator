from nicegui import ui
from typing import Dict, List
from constants.device_templates import ROOM_TYPES
from datetime import datetime
from loguru import logger

class FloorPlan:
    """Floor plan visualization component"""
    def __init__(self):
        self.rooms: Dict[str, Dict] = {}
        self.alerts = []
        self.main_container = None
        self.sensor_states = {}  # Store sensor states
        logger.debug("Initialized FloorPlan UI component")
        
    def create_floor_plan(self):
        """Create the floor plan visualization"""
        logger.info("Creating floor plan visualization")
        with ui.card().classes('w-full') as self.main_container:
            ui.label('Smart Home Floor Plan').classes('text-h6')
            
            # Create grid layout for rooms
            with ui.grid(columns=3).classes('w-full gap-4 p-4'):
                for room_type in ROOM_TYPES:
                    self._create_room_card(room_type)
        logger.debug("Floor plan visualization created successfully")

    def _create_room_card(self, room_type: str) -> None:
        """Create a card for a room type"""
        logger.debug(f"Creating room card for {room_type}")
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
                'devices': [],
                'ui_initialized': False
            }
        logger.debug(f"Room card created for {room_type}")

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
        icon = icons.get(room_name, 'home')
        logger.debug(f"Retrieved icon '{icon}' for room {room_name}")
        return icon

    def update_room_data(self, room_type: str, devices: list) -> None:
        """Update the data for a room"""
        if room_type not in self.rooms:
            logger.warning(f"Attempted to update non-existent room: {room_type}")
            return
        
        logger.info(f"Updating room data for {room_type} with {len(devices)} devices")
        room = self.rooms[room_type]
        device_container = room['device_container']
        
        try:
            # Create or update UI elements
            device_container.clear()  # Always clear and rebuild
            
            # Add devices and their sensors
            for device in devices:
                with device_container:
                    with ui.expansion(device['name'], icon='devices').classes('w-full'):
                        with ui.column().classes('w-full'):
                            for sensor in device['sensors']:
                                sensor_key = f"{room_type}_{device['name']}_{sensor['name']}"
                                
                                # Create or update sensor state
                                if sensor_key not in self.sensor_states:
                                    self.sensor_states[sensor_key] = ui.state({
                                        'current': sensor['current_value'],
                                        'base': sensor['base_value'],
                                        'unit': sensor['unit']
                                    })
                                else:
                                    self.sensor_states[sensor_key].current = sensor['current_value']
                                    self.sensor_states[sensor_key].unit = sensor['unit']
                                
                                with ui.row().classes('w-full justify-between items-center'):
                                    # Left side: sensor name and icon
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon(self._get_sensor_icon(sensor['name'])).classes('text-primary')
                                        ui.label(f"{sensor['name']}:").classes('font-bold')
                                    
                                    # Right side: current value and unit
                                    with ui.row().classes('items-center gap-2'):
                                        ui.label().bind_text(
                                            self.sensor_states[sensor_key], 
                                            'current',
                                            lambda x: f"{x:.1f}"
                                        ).classes('text-lg font-bold text-primary')
                                        ui.label().bind_text(
                                            self.sensor_states[sensor_key], 
                                            'unit'
                                        ).classes('text-sm text-gray-600')
                                    
                                    # Base value
                                    ui.label().bind_text(
                                        self.sensor_states[sensor_key],
                                        'base',
                                        lambda x: f"(Base: {x:.1f})"
                                    ).classes('text-xs text-gray-500')
            
            # Force update of the device container
            device_container.update()
            
        except Exception as e:
            logger.error(f"Error updating room data: {str(e)}")
            logger.exception(e)

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

    def add_alert(self, room_name: str, message: str):
        """Add an alert to a room"""
        if room_name not in self.rooms:
            logger.warning(f"Attempted to add alert to non-existent room: {room_name}")
            return
            
        logger.info(f"Adding alert to room {room_name}: {message}")
        self.alerts.append({
            'room': room_name,
            'message': message,
            'timestamp': datetime.now()
        })
        
        alert_container = self.rooms[room_name]['alert_container']
        if not alert_container:
            logger.warning(f"Alert container not found for room {room_name}")
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
        logger.debug(f"Added {len(room_alerts)} alerts to room {room_name}")

    def clear_alerts(self, room_name: str = None):
        """Clear alerts for a room or all rooms"""
        if room_name:
            logger.info(f"Clearing alerts for room {room_name}")
            self.alerts = [alert for alert in self.alerts if alert['room'] != room_name]
            alert_container = self.rooms[room_name]['alert_container']
            if alert_container:
                alert_container.clear()
                logger.debug(f"Cleared alert container for room {room_name}")
        else:
            logger.info("Clearing alerts for all rooms")
            self.alerts = []
            for room_name, room in self.rooms.items():
                if 'alert_container' in room and room['alert_container']:
                    room['alert_container'].clear()
                    logger.debug(f"Cleared alert container for room {room_name}") 