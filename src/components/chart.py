from nicegui import ui
from src.constants.units import UNITS
from src.constants.sensor_errors import *
from src.models.sensor import Sensor
from loguru import logger


class Chart:
    '''Chart component for displaying time series data'''

    def __init__(self):
        self.wrapper = None
        self.chart = None
        self.setup()

    def setup(self):
        '''Sets up initial UI elements of the chart'''

        with ui.row().classes('w-full h-64 justify-center items-center') as wrapper:
            self.wrapper = wrapper
            self.note_label = ui.label(
                "Keine Daten").classes("w-full text-center -translate-y-full")

    def show_note(self, text, force=False):
        '''Shows a note on the chart'''

        if force:
            self.wrapper.clear()
            with self.wrapper:
                self.note_label = ui.label(text).classes("w-full text-center -translate-y-full")
        else:
            self.note_label.set_text(text)

    def show(self, sensor=None, time_series_data=None, data=None):
        '''Shows the chart'''

        # Prepare data
        if time_series_data is not None:
            sensor_id = time_series_data[0]["sensorId"]
            sensor = Sensor.get_by_id(sensor_id)
            data = [
                [  
                    time_series_data[i]["timestamp"].strftime("%d.%m.%Y, %H:%M:%S"), time_series_data[i]["value"]
                ]
                for i in range(len(time_series_data))
            ]

        # Prepare x axis
        x_values = [i * sensor.interval for i in range(len(data))]

        try:
            self.wrapper.clear()
        except:
            pass

        # Draw chart
        with self.wrapper:
            self.chart = ui.chart({
                "title": False,
                "series": [
                    {
                        "name": sensor.name,
                        "data": data,
                    },
                ],
                "yAxis": {
                    "title": {
                        "text": UNITS[sensor.unit]["name"]
                    },
                    "labels": {
                        "format": "{value} " + UNITS[sensor.unit]["unit_abbreviation"]
                    },
                    "plotBands": [ {
                            "color": 'rgba(0, 0, 255, 0.05)',
                            "from": sensor.base_value - sensor.variation_range,
                            "to": sensor.base_value + sensor.variation_range,
                        }
                    ]
                },
                "xAxis": {
                    "title": {
                        "text": "Zeit"
                    },
                    "labels": {
                        "format": "{value}s"
                    },
                    "categories": x_values,
                },
            }).classes("w-full h-64")

    def update(self, sensor, time_series_data):
        '''Updates the chart with new data'''

        data = [[time_series_data[i]["timestamp"].strftime("%d.%m.%Y, %H:%M:%S"), time_series_data[i]["value"]]
                for i in range(len(time_series_data))]

        # Update data
        self.chart.options["series"][0]["data"] = data
        self.update_legend(sensor)

    def update_legend(self, sensor):
        '''Updates the chart legend'''

        if self.chart is None or sensor is None:
            self.empty()
            return

        # Update y axis
        self.chart.options["yAxis"]["title"]["text"] = UNITS[sensor.unit]["name"]
        self.chart.options["yAxis"]["labels"]["format"] = "{value} " + \
            UNITS[sensor.unit]["unit_abbreviation"]

        # Update dataset name
        self.chart.options["series"][0]["name"] = sensor.name
        self.chart.update()

    def update_visualization(self, sensor):
        '''Updates the chart visualization'''

        if self.chart is None:
            return
        
        # If uncommented, the chart will be zoomed in on the sensors range
        # self.chart.options["yAxis"]["min"] = sensor.base_value - sensor.variation_range - sensor.change_rate
        # self.chart.options["yAxis"]["max"] = sensor.base_value + sensor.variation_range + sensor.change_rate

        self.chart.options["yAxis"]["plotBands"] = [ {
                            "color": 'rgba(0, 0, 255, 0.05)',
                            "from": sensor.base_value - sensor.variation_range,
                            "to": sensor.base_value + sensor.variation_range,
                        }
                    ]

    def append_data_point(self, sensor, timestamp, value):
        '''Appends a data point to the chart'''

        # Append data point
        data = self.chart.options["series"][0]["data"]
        data.append([timestamp, value])
        self.chart.options["series"][0]["data"] = data

        # Update x axis
        x_values = self.chart.options["xAxis"]["categories"]
        x_values.append(x_values[-1] + sensor.interval)
        self.chart.options["xAxis"]["categories"] = x_values

        # Update dataset name
        self.chart.options["series"][0]["name"] = sensor.name
        self.chart.update()

    def empty(self):
        '''Empties the chart'''
        
        if self.chart is None:
            return
        
        self.chart.options["series"][0]["name"] = "Leer"
        self.chart.options["series"][0]["data"] = []
        self.chart.update()
