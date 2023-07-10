from nicegui import ui
from model.sensor import Sensor
from model.device import Device
from constants.units import *
from constants.sensor_errors import *
import json


class SensorItem:

    def __init__(self, sensor, delete_callback):
        self.item = None
        self.sensor = sensor
        self.visible = True
        self.error_definition = None

        error_type = None
        if sensor.error_definition:
            self.error_definition = json.loads(sensor.error_definition) if sensor.error_definition else None
            error_type = self.error_definition["type"]
        
        with ui.row().bind_visibility(self, "visible").classes("px-3 py-4 flex justify-between items-center w-full hover:bg-gray-50") as row:
            self.item = row
            with ui.row().classes("gap-6"):
                ui.label(f"{sensor.id}").classes("w-[30px]")
                ui.label(f"{sensor.name}").classes("w-[130px]")
                ui.label(f"{UNITS[sensor.unit]['name']}").classes("w-[130px]")
                if sensor.device:
                    self.device_name_label = ui.label(sensor.device.name).classes("w-[130px]")
                if error_type:
                    ui.label(f"{SENSOR_ERRORS_UI_MAP[error_type]}").classes("w-[130px]")
            with ui.row():
                with ui.row().classes("gap-2"):
                    ui.button(icon="info_outline", on_click=self.show_details_dialog).props(
                        "flat").classes("px-2")
                    ui.button(icon="delete", on_click=lambda s=sensor: delete_callback(s)).props(
                        "flat").classes("px-2 text-red")

    def show_details_dialog(self):
        with ui.dialog(value=True) as dialog, ui.card().classes("px-6 pb-6 w-[696px] !max-w-none min-h-[327px]"):
            self.dialog = dialog
            with ui.row().classes("mb-8 w-full justify-between items-center"):
                ui.label(f"{self.sensor.name}").classes("text-lg font-medium")
                with ui.tabs().classes('') as tabs:
                    general_tab = ui.tab('Allgemein')
                    simulation_tab = ui.tab('Simulation')
                ui.button(icon="close", on_click=self.dialog.close).props("flat").classes("px-2 text-black")

            with ui.tab_panels(tabs, value=general_tab).classes('w-full'):
                with ui.tab_panel(general_tab).classes("p-0"):

                    with ui.column().classes("gap-4"):
                        with ui.row().classes("gap-10"):
                            with ui.column().classes("gap-0"):
                                ui.label("ID").classes("text-sm text-gray-500")
                                ui.label(f"{self.sensor.id}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Name").classes("text-sm text-gray-500")
                                ui.label(f"{self.sensor.name}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Typ").classes("text-sm text-gray-500")
                                ui.label(f"{UNITS[self.sensor.unit]['name']}").classes("text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Einheit").classes("text-sm text-gray-500")
                                ui.label(f"{UNITS[self.sensor.unit]['unit_abbreviation']}").classes("text-md font-medium")

                    ui.row().classes("mt-4 mb-2 h-px w-full bg-gray-200 border-0")

                    with ui.column().classes("gap-1"):
                        ui.label("Gerät").classes("text-lg font-semibold mt-2")

                        with ui.column().classes("gap-2"):
                            ui.label("Wähle aus zu welchem Gerät dieser Sensor gehören soll.")
                            devices = Device.get_all()
                            device_options = {device.id: device.name for device in devices}
                            preselect_value = self.sensor.device.id if self.sensor.device else None

                            with ui.row().classes("items-center"):
                                self.device_select = ui.select(value=preselect_value, options=device_options, with_input=True).classes("min-w-[120px]")
                                ui.button("Speichern", on_click=self.change_device).props("flat")

                with ui.tab_panel(simulation_tab).classes("p-0"):
                    with ui.column().classes("gap-4"):
                        with ui.row().classes("gap-10"):
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

                    if self.error_definition:
                        ui.label("Fehlersimulation").classes("text-[16px] font-medium mt-8 mb-4")

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
        # Check if container is active
        if self._check_if_container_is_active(self.sensor.device):
            return
        
        # Check if container of new device is active
        new_device = Device.get_by_id(self.device_select.value)
        if self._check_if_container_is_active(new_device):
            return

        self.sensor.device_id = self.device_select.value
        Sensor.session.commit()
        
        self.device_name_label.text = new_device.name
        ui.notify(f"Änderung erfolgreich gespeichert.", type="positive")

    def _check_if_container_is_active(self, device):
        container = device.container
        if container is not None and container.is_active:
            ui.notify(f"Änderung kann nicht übernommen werden während Container '{container.name}' aktiv ist.", type="negative")
            return True
        return False
        