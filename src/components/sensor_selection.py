from nicegui import ui
from src.models.device import Device
from src.models.sensor import Sensor
from src.models.device import Device
from src.models.container import Container

class SensorSelection:
    '''Sensor selection component for selecting a sensor'''

    def __init__(self, container, sensor_select_callback):
        '''Initializes the sensor selection component'''
        self.container = container
        self.sensor_select_callback = sensor_select_callback
        self.row = None
        self.setup()
            
    def setup(self):
        '''Sets up the UI elements of the sensor selection component'''
        device_options = {
            device.id: device.name for device in self.container.devices}
        first_device = self.container.devices[0]
        first_sensor = first_device.sensors[0] if len(
            first_device.sensors) > 0 else None
        sensor_options = {
            sensor.id: sensor.name for sensor in self.container.devices[0].sensors}

        with ui.row().classes("mb-5") as row:
            self.row = row
            self.device_select = ui.select(device_options, value=first_device.id,
                                           label="Device", on_change=self.device_select_change_handler).classes("w-32")
            first_sensor_value = first_sensor.id if first_sensor is not None else -1
            self.sensor_select = ui.select(sensor_options, value=first_sensor_value,
                                           label="Sensor", on_change=self.sensor_select_change_handler).classes("w-32")
            
    def device_select_change_handler(self):
        '''Handles the change event of the device select'''
        device_id = self.device_select.value
        device = Device.get_by_id(device_id)

        if len(device.sensors) > 0:
            # Preselect first sensor
            sensor_options = {
                sensor.id: sensor.name for sensor in device.sensors}
            self.sensor_select.options = sensor_options
            first_value = list(sensor_options.keys())[0]
            self.sensor_select.update()
            self.sensor_select.value = first_value
        else:
            # No sensors available
            self.sensor_select.options = {-1: "Empty"}
            self.sensor_select.value = -1
            self.sensor_select.update()

    def sensor_select_change_handler(self):
        '''Handles the change event of the sensor select'''
        sensor = Sensor.get_by_id(self.sensor_select.value)
        self.sensor_select_callback(sensor)

    def get_device(self):
        '''Returns the selected device'''
        return Device.get_by_id(self.device_select.value)

    def get_sensor(self):
        '''Returns the selected sensor'''
        return Sensor.get_by_id(self.sensor_select.value)