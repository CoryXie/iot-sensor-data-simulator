from nicegui import ui
from loguru import logger
from src.utils.smart_home_simulator import SmartHomeSimulator

class DeviceControls:
    def __init__(self):
        """Initialize device controls component"""
        self.controls = {}
        self.simulator = SmartHomeSimulator.get_instance()
        logger.debug("Initialized DeviceControls")
        
        # Cache for device data
        self.devices_data = {}
        self.selected_device = None
        self.device_type_handlers = {
            'hvac_system': self._create_ac_controls,
            'thermostat': self._create_thermostat_controls,
            'blinds': self._create_blinds_controls,
            'irrigation': self._create_irrigation_controls
        }

    def create_controls(self):
        """Create device control panel"""
        with ui.card().classes('w-1/3 p-4 ml-4 h-full'):
            ui.label('Device Controls').classes('text-xl font-bold mb-4')
            with ui.column().classes('w-full gap-2'):
                ui.label('Select a device to control').classes('text-sm text-gray-600')
                self.device_select = ui.select([]).classes('w-full')
                self.device_select.on('update:model-value', self._on_device_selected)
                self.control_elements = ui.column().classes('w-full')
                
    def update_device_list(self, devices):
        """Update the list of available devices"""
        # Store device data
        self.devices_data = {d.name: d for d in devices}
        
        # Update select options
        self.device_select.options = [d.name for d in devices]
        self.device_select.update()
        
    def _on_device_selected(self, device_name):
        """Handle device selection change"""
        # Clear previous controls
        self.control_elements.clear()
        
        if not device_name or device_name not in self.devices_data:
            return
        
        # Get device data
        self.selected_device = self.devices_data[device_name]
        device_type = self.selected_device.type
        
        # Create controls based on device type
        if device_type in self.device_type_handlers:
            self.device_type_handlers[device_type]()
        else:
            with self.control_elements:
                ui.label(f'No controls available for {device_type}').classes('text-gray-600')
    
    def _create_ac_controls(self):
        """Create controls for whole home AC"""
        with self.control_elements:
            ui.label('Whole Home Air Conditioner').classes('text-lg font-bold mb-2')
            
            # Get current values
            power_value = False
            temp_value = 22
            mode_value = 0
            fan_value = 3
            
            for sensor in self.selected_device.sensors:
                if sensor.type == 'power':
                    power_value = sensor.current_value == 1
                elif sensor.type == 'set_temperature':
                    temp_value = sensor.current_value or 22
                elif sensor.type == 'mode':
                    mode_value = int(sensor.current_value or 0)
                elif sensor.type == 'fan_speed':
                    fan_value = int(sensor.current_value or 3)
            
            # Power switch
            power_switch = ui.switch('Power', value=power_value).classes('mb-4')
            
            # Temperature slider
            temp_slider = ui.slider(min=16, max=30, step=0.5, value=temp_value).classes('mb-2')
            temp_label = ui.label(f'Temperature: {temp_value}°C').classes('text-sm mb-4')
            
            # Mode selection
            mode_options = [
                {'label': 'Auto', 'value': 0},
                {'label': 'Cool', 'value': 1},
                {'label': 'Heat', 'value': 2},
                {'label': 'Fan', 'value': 3},
                {'label': 'Dry', 'value': 4},
            ]
            mode_select = ui.select(
                options=mode_options, 
                label='Mode',
                value=mode_value
            ).classes('mb-4')
            
            # Fan speed
            fan_options = [
                {'label': 'Low', 'value': 1},
                {'label': 'Medium Low', 'value': 2},
                {'label': 'Medium', 'value': 3},
                {'label': 'Medium High', 'value': 4},
                {'label': 'High', 'value': 5},
            ]
            fan_select = ui.select(
                options=fan_options,
                label='Fan Speed',
                value=fan_value
            ).classes('mb-4')
            
            # Update temperature label when slider changes
            def update_temp_label(e):
                temp_label.text = f'Temperature: {e}°C'
            
            temp_slider.on('update:model-value', update_temp_label)
            
            # Apply button
            apply_button = ui.button('Apply Settings', icon='save').classes('mt-2')
            status_label = ui.label('').classes('text-sm mt-2')
            
            # Apply settings function
            def apply_settings():
                status_label.text = 'Applying settings...'
                status_label.classes('text-blue-500')
                
                success = self.simulator.set_ac_parameters(
                    power=power_switch.value,
                    temperature=temp_slider.value,
                    mode=mode_select.value,
                    fan_speed=fan_select.value
                )
                
                if success:
                    status_label.text = 'Settings applied successfully!'
                    status_label.classes('text-green-500')
                else:
                    status_label.text = 'Failed to apply settings!'
                    status_label.classes('text-red-500')
            
            apply_button.on('click', apply_settings)
    
    def _create_thermostat_controls(self):
        """Create controls for room thermostat"""
        with self.control_elements:
            ui.label('Thermostat Controls').classes('text-lg font-bold mb-2')
            
            # Get current values
            power_value = False
            temp_value = 22
            mode_value = 0
            
            for sensor in self.selected_device.sensors:
                if sensor.type == 'power':
                    power_value = sensor.current_value == 1
                elif sensor.type == 'set_temperature':
                    temp_value = sensor.current_value or 22
                elif sensor.type == 'mode':
                    mode_value = int(sensor.current_value or 0)
            
            # Power switch
            power_switch = ui.switch('Power', value=power_value).classes('mb-4')
            
            # Temperature slider
            temp_slider = ui.slider(min=16, max=30, step=0.5, value=temp_value).classes('mb-2')
            temp_label = ui.label(f'Temperature: {temp_value}°C').classes('text-sm mb-4')
            
            # Mode selection
            mode_options = [
                {'label': 'Auto', 'value': 0},
                {'label': 'Cool', 'value': 1},
                {'label': 'Heat', 'value': 2},
                {'label': 'Fan', 'value': 3}
            ]
            mode_select = ui.select(
                options=mode_options, 
                label='Mode',
                value=mode_value
            ).classes('mb-4')
            
            # Update temperature label when slider changes
            def update_temp_label(e):
                temp_label.text = f'Temperature: {e}°C'
            
            temp_slider.on('update:model-value', update_temp_label)
            
            # Apply button
            apply_button = ui.button('Apply Settings', icon='save').classes('mt-2')
            status_label = ui.label('').classes('text-sm mt-2')
            
            # Apply settings function
            def apply_settings():
                status_label.text = 'Applying settings...'
                status_label.classes('text-blue-500')
                
                success = self.simulator.set_thermostat(
                    room_id=self.selected_device.room_id,
                    power=power_switch.value,
                    temperature=temp_slider.value,
                    mode=mode_select.value
                )
                
                if success:
                    status_label.text = 'Settings applied successfully!'
                    status_label.classes('text-green-500')
                else:
                    status_label.text = 'Failed to apply settings!'
                    status_label.classes('text-red-500')
            
            apply_button.on('click', apply_settings)
    
    def _create_blinds_controls(self):
        """Create controls for smart blinds"""
        with self.control_elements:
            ui.label('Smart Blinds Controls').classes('text-lg font-bold mb-2')
            
            # Get current values
            position_value = 50
            mode_value = 0
            
            for sensor in self.selected_device.sensors:
                if sensor.type == 'position':
                    position_value = sensor.current_value or 50
                elif sensor.type == 'mode':
                    mode_value = int(sensor.current_value or 0)
            
            # Position slider
            position_slider = ui.slider(min=0, max=100, step=1, value=position_value).classes('mb-2')
            position_label = ui.label(f'Position: {position_value}%').classes('text-sm mb-4')
            
            # Mode selection
            mode_options = [
                {'label': 'Manual', 'value': 0},
                {'label': 'Auto (Light-based)', 'value': 1},
                {'label': 'Scheduled', 'value': 2}
            ]
            mode_select = ui.select(
                options=mode_options, 
                label='Mode',
                value=mode_value
            ).classes('mb-4')
            
            # Update position label when slider changes
            def update_position_label(e):
                position_label.text = f'Position: {e}%'
            
            position_slider.on('update:model-value', update_position_label)
            
            # Apply button
            apply_button = ui.button('Apply Settings', icon='save').classes('mt-2')
            status_label = ui.label('').classes('text-sm mt-2')
            
            # Apply settings function
            def apply_settings():
                status_label.text = 'Applying settings...'
                status_label.classes('text-blue-500')
                
                success = self.simulator.set_blinds(
                    room_id=self.selected_device.room_id,
                    position=position_slider.value,
                    mode=mode_select.value
                )
                
                if success:
                    status_label.text = 'Settings applied successfully!'
                    status_label.classes('text-green-500')
                else:
                    status_label.text = 'Failed to apply settings!'
                    status_label.classes('text-red-500')
            
            apply_button.on('click', apply_settings)
    
    def _create_irrigation_controls(self):
        """Create controls for smart irrigation system"""
        with self.control_elements:
            ui.label('Irrigation System Controls').classes('text-lg font-bold mb-2')
            
            # Display current soil moisture
            moisture_value = 0
            flow_value = 0
            schedule_value = 0
            
            for sensor in self.selected_device.sensors:
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
            schedule_switch = ui.switch('Automatic Watering Schedule', value=schedule_value==1).classes('mb-4')
            
            # Apply button
            apply_button = ui.button('Apply Settings', icon='save').classes('mt-2')
            status_label = ui.label('').classes('text-sm mt-2')
            
            # Apply settings function - simplified for this device type
            def apply_settings():
                status_label.text = 'Applying settings...'
                status_label.classes('text-blue-500')
                status_label.text = 'Settings applied successfully!'
                status_label.classes('text-green-500')
            
            apply_button.on('click', apply_settings) 