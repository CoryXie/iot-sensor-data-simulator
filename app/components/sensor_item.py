from nicegui import ui
from model.sensor import Sensor
from model.device import Device
from constants.units import *
from constants.sensor_errors import *
import json
from loguru import logger


class SensorItem:
    '''Sensor item component for displaying a sensor in a list'''

    def __init__(self, sensor, delete_callback):
        '''Initializes the sensor item'''
        self.item = None
        self.sensor = sensor
        self.visible = True
        self.error_definition = None
        self.setup(sensor, delete_callback)
    
    def setup(self, sensor, delete_callback):
        '''Sets up the UI elements of the sensor item'''
        error_type = None
        if sensor.error_definition:
            self.error_definition = json.loads(sensor.error_definition) if sensor.error_definition else None
            error_type = self.error_definition["type"]

        # Find the unit by ID
        unit_info = next((unit for unit in UNITS if unit['id'] == sensor.unit), {'name': 'Unknown', 'symbol': '', 'unit_abbreviation': ''})
        logger.debug(f"Found unit info for sensor {sensor.id}: {unit_info}")
        
        # Get the unit display - prefer unit_abbreviation, fallback to symbol
        unit_display = unit_info.get('unit_abbreviation', unit_info.get('symbol', ''))

        with ui.row().bind_visibility(self, "visible").classes("px-3 py-4 flex justify-between items-center w-full hover:bg-gray-50") as row:
            self.item = row
            with ui.row().classes("gap-6"):
                ui.label(f"{sensor.id}").classes("w-[30px]")
                ui.label(f"{sensor.name}").classes("w-[130px]")
                ui.label(f"{unit_info['name']}").classes("w-[130px]")
                self.device_name_label = ui.label(sensor.device.name if sensor.device else "").classes("w-[130px]")
                ui.label(f"{SENSOR_ERRORS_UI_MAP[error_type]}" if error_type else "").classes("w-[130px]")
            with ui.row():
                with ui.row().classes("gap-2"):
                    ui.button(icon="info_outline", on_click=self.show_details_dialog).props(
                        "flat").classes("px-2")
                    ui.button(icon="delete", on_click=lambda s=sensor: delete_callback(s)).props(
                        "flat").classes("px-2 text-red")

    def show_details_dialog(self):
        '''Shows the details dialog for a sensor'''
        # Find the unit by ID
        unit_info = next((unit for unit in UNITS if unit['id'] == self.sensor.unit), {'name': 'Unknown', 'symbol': '', 'unit_abbreviation': ''})
        # Get the unit display - prefer unit_abbreviation, fallback to symbol
        unit_display = unit_info.get('unit_abbreviation', unit_info.get('symbol', ''))

        with ui.dialog(value=True) as dialog, ui.card().classes("px-6 pb-6 w-[696px] !max-w-none min-h-[327px]"):
            self.dialog = dialog
            with ui.row().classes("relative mb-8 w-full justify-between items-center"):
                ui.label(f"{self.sensor.name}").classes("text-lg font-medium")
                # Setup tabs
                with ui.tabs().classes('') as tabs:
                    general_tab = ui.tab('Allgemein')
                    simulation_tab = ui.tab('Simulation')
                ui.row()
                ui.button(icon="close", on_click=self.dialog.close).props("flat").classes("absolute top-0 right-0 px-2 text-black md:top-1")

            # Setup tab panels
            with ui.tab_panels(tabs, value=general_tab).classes('w-full'):

                # Setup general tab to show general sensor settings
                with ui.tab_panel(general_tab).classes("p-0"):
                    with ui.column().classes("gap-4"):
                        with ui.row().classes("gap-x-10 gap-y-4"):
                            with ui.column().classes("gap-0"):
                                ui.label("ID").classes("text-sm text-gray-500")
                                ui.label(f"{self.sensor.id}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Name").classes("text-sm text-gray-500")
                                ui.label(f"{self.sensor.name}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Typ").classes("text-sm text-gray-500")
                                ui.label(f"{unit_info['name']}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Einheit").classes("text-sm text-gray-500")
                                ui.label(f"{unit_display}").classes("text-md font-medium")

                    ui.row().classes("mt-4 mb-2 h-px w-full bg-gray-200 border-0")

                    with ui.column().classes("gap-1"):
                        ui.label("Device").classes("text-lg font-semibold mt-2")

                        with ui.column().classes("gap-2"):
                            ui.label("Select which device this sensor should belong to.")
                            devices = Device.get_all()
                            device_options = {device.id: device.name for device in devices}
                            preselect_value = self.sensor.device.id if self.sensor.device else None

                            with ui.row().classes("items-center"):
                                self.device_select = ui.select(value=preselect_value, options=device_options, with_input=True).classes("min-w-[120px]")
                                ui.button("Speichern", on_click=self.change_device).props("flat")

                # Setup simulation tab to show sensor simulation settings
                with ui.tab_panel(simulation_tab).classes("p-0"):
                    with ui.column().classes("gap-4"):
                        with ui.row().classes("gap-x-10 gap-y-4"):
                            with ui.column().classes("gap-0"):
                                ui.label("Basiswert").classes("text-sm text-gray-500")
                                ui.label(f"{self.sensor.base_value}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Variationsbereich").classes("text-sm text-gray-500")
                                ui.label(f"{self.sensor.variation_range}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Änderungsrate +/-").classes("text-sm text-gray-500")
                                ui.label(f"{self.sensor.change_rate}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Interval [s]").classes("text-sm text-gray-500")
                                ui.label(f"{self.sensor.interval}").classes("text-md font-medium")

                    # Show error simulation settings if error definition is set
                    if self.error_definition:
                        ui.label("Error Simulation").classes("text-[16px] font-medium mt-8 mb-4")

                        with ui.grid().classes("grid grid-cols-2 gap-x-10"):
                            for key, value in self.error_definition.items():
                                with ui.column().classes("gap-0"):
                                    ui.label(f"{SENSOR_ERRORS_UI_MAP[key]}").classes("text-sm text-gray-500")

                                    if key == "type":
                                        ui.label(f"{SENSOR_ERRORS_UI_MAP[value]}").classes("text-md font-medium")
                                    else:
                                        formatted_value = f"{float(value) * 100}%" if "probability" in key else f"{value}"
                                        ui.label(formatted_value).classes("text-md font-medium")
    
    def change_device(self):
        '''Changes the device of the sensor'''

        # Check if container is active
        if self._check_if_container_is_active():
            return
        
        # Check if container of new device is active
        new_device = Device.get_by_id(self.device_select.value)
        if self._check_if_container_is_active(new_device):
            return

        self.sensor.device_id = self.device_select.value
        Sensor.session.commit()
        
        self.device_name_label.text = new_device.name
        ui.notify(f"Changes saved successfully.", type="positive")

    def _check_if_container_is_active(self):
        '''Checks if the parent container is active'''
        container = self.sensor.container
        if container is not None and container.is_active:
            ui.notify(f"Änderung kann nicht übernommen werden während Container '{container.name}' aktiv ist.", type="negative")
            return True
        return False
        