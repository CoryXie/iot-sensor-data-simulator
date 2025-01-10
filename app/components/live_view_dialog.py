from nicegui import ui
from constants.units import *
from components.sensor_selection import SensorSelection
from components.chart import Chart


class LiveViewDialog():
    '''This class represents the live view dialog. It is used to display sensor data in a diagram in realtime.'''

    def __init__(self, parent):
        '''Initializes the live view dialog'''
        self.parent = parent
        self.dialog = None
        self.chart = None
        self.setup()

    def setup(self):
        '''Sets up the UI elements of the dialog'''
        with self.parent:
            with ui.dialog() as dialog, ui.card().classes("w-[696px] !max-w-none"):
                self.dialog = dialog
                with ui.row().classes("w-full justify-between items-center"):
                    self.title_label = ui.label().classes("text-lg font-semibold")
                    ui.button(icon="close", on_click=self.dialog.close).props(
                        "flat").classes("px-2 text-black")
                with ui.row().classes():
                    self.selects_row = ui.row().classes("mb-5")

                self.chart = Chart()

    def show(self, container):
        '''Shows the dialog'''
        self.title_label.set_text(f"Live View: {container.name}")
        self.selects_row.clear()

        with self.selects_row:
            self.sensor_selection = SensorSelection(
                container=container, sensor_select_callback=self.sensor_select_change_handler)
        
        # Prepare chart
        self.chart.empty()
        text = "Waiting for sensor data..." if container.is_active else "Container is not active"
        self.chart.show_note(text)
        sensor = self.sensor_selection.get_sensor()
        self.chart.update_legend(sensor=sensor)
        self.chart.update_visualization(sensor=sensor)

        self.dialog.open()

    def sensor_select_change_handler(self, sensor):
        '''Handles the sensor select change event'''
        self.chart.empty()
        self.chart.show_note("Waiting for sensor data...")
        self.chart.update_legend(sensor=sensor)
        self.chart.update_visualization(sensor=sensor)

    def append_data_point(self, sensor, timestamp, value):
        '''Appends a data point to the chart'''

        # Return if the dialog is not open
        if not self.dialog.value:
            return

        # Only append value if the correct device and the sensor is selected
        if self.sensor_selection.device_select.value != sensor.device_id or self.sensor_selection.sensor_select.value != sensor.id:
            return

        # Show/create chart if not already done
        if self.chart.chart is None:
            self.chart.show(sensor=sensor, data=[[timestamp, value]])
            return

        # Append data point
        self.chart.append_data_point(
            sensor=sensor, timestamp=timestamp, value=value)
