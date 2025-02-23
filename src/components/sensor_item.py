from nicegui import ui
from loguru import logger
from typing import Callable
from src.models.sensor import Sensor
from src.models.device import Device
from src.models.container import Container
from src.database import db_session
from sqlalchemy.orm import joinedload
from src.components.sensor_time_series import SensorTimeSeries
from datetime import datetime, timedelta
import asyncio


class SensorItem:
    """Component for displaying and managing a sensor item"""
    
    def __init__(self, sensor_id: int, delete_callback: Callable = None, sensor: Sensor = None):
        """Initialize the sensor item"""
        self.sensor_id = sensor_id
        self.time_series = SensorTimeSeries(max_points=100)
        self.update_task = None
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
                device_name = refreshed_sensor.device.name if refreshed_sensor.device else "No Device"
                container = refreshed_sensor.device.container if refreshed_sensor.device else None
                
                # Store sensor info for updates
                self.sensor_type = refreshed_sensor.type
                self.sensor_unit = refreshed_sensor.unit
                
                with ui.card().classes('w-full p-4'):
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.column().classes('flex-grow'):
                            ui.label(f'Name: {refreshed_sensor.name}').classes('text-lg font-bold')
                            ui.label(f'Type: {refreshed_sensor.type}')
                            ui.label(f'Base Value: {refreshed_sensor.base_value} {refreshed_sensor.unit}')
                            
                            if refreshed_sensor.device:
                                ui.label(f'Device: {device_name}')
                                ui.label(f'Location: {refreshed_sensor.device.location}')
                            
                            if refreshed_sensor.type == 'continuous':
                                ui.label(f'Variation Range: {refreshed_sensor.variation_range}')
                                ui.label(f'Change Rate: {refreshed_sensor.change_rate}')
                            
                            error_def = getattr(refreshed_sensor, 'error_definition', None)
                            if error_def:
                                ui.label(f'Error Definition: {error_def}').classes('text-red-500')
                        
                        with ui.column().classes('justify-end gap-2'):
                            ui.button('Details', on_click=lambda: self.show_details_dialog()).classes('bg-blue-500')
                            if delete_callback:
                                ui.button('Delete', on_click=lambda: self.cleanup_and_delete(delete_callback)).classes('bg-red-500')
                    
                    # Add time series plot
                    self.plot_container = ui.element('div').classes('w-full mt-4')
                    with self.plot_container:
                        self.time_series_plot = self.time_series.create_plot(
                            sensor_type=refreshed_sensor.type,
                            unit=refreshed_sensor.unit
                        )
                    
                    # Start update task
                    self.start_updates()
                
        except Exception as e:
            logger.error(f"Error setting up sensor item: {str(e)}")
            with ui.card().classes('w-full'):
                ui.label(f'Error displaying sensor: {sensor_id}').classes('text-red-500')
    
    async def update_time_series(self):
        """Update time series data periodically"""
        try:
            while True:
                with db_session() as session:
                    sensor = session.query(Sensor).get(self.sensor_id)
                    if sensor:
                        # Add new data point
                        self.time_series.add_point(sensor.current_value)
                        
                        # Update plot
                        with self.plot_container:
                            self.time_series_plot.clear()
                            self.time_series_plot = self.time_series.create_plot(
                                sensor_type=self.sensor_type,
                                unit=self.sensor_unit
                            )
                        
                        # Check if sensor status changed
                        if not sensor.is_active:
                            self.time_series.add_status_marker('Stopped')
                        
                await asyncio.sleep(5)  # Update every 5 seconds
        except Exception as e:
            logger.error(f"Error updating time series: {str(e)}")
    
    def start_updates(self):
        """Start the update task"""
        if not self.update_task:
            self.update_task = asyncio.create_task(self.update_time_series())
    
    def cleanup_and_delete(self, delete_callback):
        """Clean up update task and delete sensor"""
        if self.update_task:
            self.update_task.cancel()
        delete_callback(self.sensor_id)
    
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