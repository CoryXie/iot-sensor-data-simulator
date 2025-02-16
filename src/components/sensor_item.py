from nicegui import ui
from loguru import logger
from typing import Callable
from src.models.sensor import Sensor
from src.models.device import Device
from src.models.container import Container
from src.database import db_session
from sqlalchemy.orm import joinedload


class SensorItem:
    """Component for displaying and managing a sensor item"""
    
    def __init__(self, sensor_id: int, delete_callback: Callable = None, sensor: Sensor = None):
        """Initialize the sensor item"""
        self.sensor_id = sensor_id
        self.setup(sensor_id, delete_callback, sensor)
    
    def setup(self, sensor_id: int, delete_callback: Callable = None, sensor: Sensor = None):
        """Initialize sensor item with proper session handling"""
        try:
            with db_session() as session:
                if not sensor:
                    sensor = session.query(Sensor).options(
                        joinedload(Sensor.device)
                    ).filter_by(id=sensor_id).first()
                
                if not sensor:
                    logger.error(f"Sensor {sensor_id} not found")
                    return
                
                refreshed_sensor = session.merge(sensor)
                device_name = refreshed_sensor.device.name
                container = refreshed_sensor.device.container
                
                with ui.card().classes('sensor-card'):
                    ui.label(f"{device_name} - {refreshed_sensor.name}")
                    ui.label(f"Value: {refreshed_sensor.current_value}{refreshed_sensor.unit}")
                
                self.device_name = device_name
                
                with ui.card().classes('w-full'):
                    with ui.row().classes('w-full items-center'):
                        with ui.column().classes('flex-grow'):
                            ui.label(f'Name: {refreshed_sensor.name}').classes('text-lg font-bold')
                            ui.label(f'Type: {refreshed_sensor.type}')
                            ui.label(f'Base Value: {refreshed_sensor.base_value} {refreshed_sensor.unit}')
                            ui.label(f'Sensor Type: {refreshed_sensor.type}')
                            
                            if refreshed_sensor.device:
                                ui.label(f'Device: {refreshed_sensor.device.name}')
                                ui.label(f'Location: {refreshed_sensor.device.location}')
                            
                            if refreshed_sensor.type == 'continuous':
                                ui.label(f'Variation Range: {refreshed_sensor.variation_range}')
                                ui.label(f'Change Rate: {refreshed_sensor.change_rate}')
                            
                            error_def = getattr(refreshed_sensor, 'error_definition', None)
                            if error_def:
                                ui.label(f'Error Definition: {error_def}').classes('text-red-500')
                        
                        with ui.column().classes('justify-end'):
                            ui.button('Details', on_click=lambda: self.show_details_dialog()).classes('bg-blue-500')
                            if delete_callback:
                                ui.button('Delete', on_click=lambda: delete_callback(refreshed_sensor.id)).classes('bg-red-500')
        except Exception as e:
            logger.error(f"Error setting up sensor item: {str(e)}")
            with ui.card().classes('w-full'):
                ui.label(f'Error displaying sensor: {sensor_id}').classes('text-red-500')

    def show_details_dialog(self):
        """Show detailed sensor information in a dialog"""
        try:
            with ui.dialog() as dialog, ui.card():
                ui.label('Sensor Details').classes('text-xl font-bold mb-4')
                
                with ui.row().classes('w-full'):
                    with ui.column().classes('flex-grow'):
                        ui.label('Basic Information').classes('text-lg font-bold')
                        ui.label(f'ID: {self.sensor_id}')
                        ui.label(f'Name: {self.device_name}')
                        ui.label(f'Type: {self.device_name}')
                        ui.label(f'Sensor Type: {self.device_name}')
                
                with ui.row().classes('w-full mt-4'):
                    with ui.column().classes('flex-grow'):
                        ui.label('Value Information').classes('text-lg font-bold')
                        ui.label(f'Base Value: {self.device_name}')
                        ui.label(f'Current Value: {self.device_name}')
                        if self.device_name == 'continuous':
                            ui.label(f'Variation Range: ±{self.device_name}')
                            ui.label(f'Change Rate: {self.device_name}')
                            ui.label(f'Update Interval: {self.device_name}')
                
                if self.device_name:
                    with ui.row().classes('w-full mt-4'):
                        with ui.column().classes('flex-grow'):
                            ui.label('Device Information').classes('text-lg font-bold')
                            ui.label(f'Device: {self.device_name}')
                            ui.label(f'Location: {self.device_name}')
                            ui.label(f'Device Type: {self.device_name}')
                
                if self.device_name:
                    with ui.row().classes('w-full mt-4'):
                        with ui.column().classes('flex-grow'):
                            ui.label('Error Information').classes('text-lg font-bold text-red-500')
                            ui.label(f'Error Definition: {self.device_name}')
                
                with ui.row().classes('w-full justify-end mt-4'):
                    ui.button('Close', on_click=dialog.close).classes('bg-gray-500')
                
                dialog.open()
        except Exception as e:
            logger.error(f"Error showing sensor details: {str(e)}")
            ui.notify(f"Error showing sensor details: {str(e)}", type='negative')