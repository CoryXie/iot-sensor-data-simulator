from nicegui import ui
from loguru import logger

class DeviceControls:
    def __init__(self):
        """Initialize device controls component"""
        self.controls = {}
        logger.debug("Initialized DeviceControls")

    def create_controls(self):
        """Create device control panel"""
        with ui.card().classes('w-1/3 p-4 ml-4 h-full'):
            ui.label('Device Controls').classes('text-xl font-bold mb-4')
            with ui.column().classes('w-full gap-2'):
                ui.label('Select a device to control').classes('text-sm text-gray-600')
                self.device_select = ui.select([]).classes('w-full')
                self.control_elements = ui.column().classes('w-full')
                
    def update_device_list(self, devices):
        """Update the list of available devices"""
        self.device_select.options = [d.name for d in devices]
        self.device_select.update() 