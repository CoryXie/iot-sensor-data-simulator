from nicegui import ui
from src.models.container import Container
from src.models.sensor import Sensor
import pyperclip
from src.components.live_view_dialog import LiveViewDialog
from src.models.device import Device

class DeviceItem:
    '''Device item component for displaying a device in a list'''

    def __init__(self, device, delete_callback):
        '''Initializes the device item'''
        self.item = None
        self.device = device
        self.visible = True
        self.setup(device, delete_callback)

    def setup(self, device, delete_callback):
        '''Sets up the UI elements of the device item'''
        with ui.row().bind_visibility(self, 'visible').classes('px-3 py-6 flex justify-between items-center w-full hover:bg-gray-50') as row:
            self.item = row
            with ui.row().classes('gap-6'):
                ui.label(f'{device.id}').classes('w-[30px]')
                ui.label(f'{device.name}').classes('w-[130px]')
                self.container_label = ui.label(device.container.name if device.container else "").classes('w-[130px]')
                self.sensor_count_label = ui.label(f'{len(device.sensors)}').classes('w-[60px]')
            with ui.row().classes('gap-2'):
                ui.button(icon="info_outline", on_click=self.show_details_dialog).props(
                    "flat").classes("px-2")
                ui.button(icon='delete', on_click=lambda d=device: delete_callback(d)).props(
                    'flat').classes('px-2 text-red')

    def show_details_dialog(self):
        '''Shows the details dialog of a device'''
        with ui.dialog(value=True) as dialog, ui.card().classes("px-6 pb-6 w-[696px] !max-w-none"):
            self.dialog = dialog
            with ui.column().classes("w-full flex flex-col md:flex-row"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label(
                        f"Details - '{self.device.name}'").classes("text-xl font-semibold")
                    ui.button(icon="close", on_click=self.dialog.close).props(
                        "flat").classes("px-2 text-black")

                with ui.row().classes("grid md:grid-cols-2 gap-4 mt-4"):
                    # General information
                    with ui.column().classes("gap-4"):
                        ui.label("General").classes("text-lg font-semibold mt-2")
                        with ui.row().classes("gap-10"):
                            with ui.column().classes("gap-0"):
                                ui.label("ID").classes("text-sm text-gray-500")
                                ui.label(f"{self.device.id}").classes(
                                    "text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Name").classes("text-sm text-gray-500")
                                ui.label(f"{self.device.name}").classes(
                                    "text-md font-medium")

                    # Container settings
                    with ui.column().classes("gap-4"):
                        ui.label("Container").classes("text-lg font-semibold mt-2")
                        with ui.column().classes("gap-2"):
                            ui.label(
                                "Select which container this device should belong to.")
                            containers = Container.get_all()
                            container_options = {
                                container.id: container.name for container in containers}
                            preselect_value = self.device.container.id if self.device.container else None

                            with ui.row().classes("items-center"):
                                self.container_select = ui.select(
                                    value=preselect_value, options=container_options, with_input=True).classes("min-w-[120px]")
                                ui.button("Save", on_click=self.change_container).props(
                                    "flat")
                
                # Show connection string
                with ui.row().classes("mt-4 p-4 w-full justify-between items-center bg-gray-100 !rounded-md"):
                    with ui.column().classes("w-[90%] gap-0"):
                        ui.label("Primary Connection String").classes("text-sm text-gray-500")

                        connection_string = self.device.connection_string
                        connection_string_is_none = connection_string is None
                        if connection_string is None:
                            connection_string = "This device has no connection to an IoT Hub"
                        ui.label(connection_string).classes("w-full text-md font-medium overflow-x-auto")
                    copy_button = ui.button(icon="content_copy", on_click=lambda: self.copy_to_clipboard(self.device.connection_string)).classes("px-2").props("flat")
                    
                    if connection_string_is_none:
                        copy_button.set_enabled(False)

                # Separator
                ui.row().classes("mt-4 mb-2 h-px w-full bg-gray-200 border-0")

                # Sensor settings
                with ui.column().classes("pl-4 gap-4"):
                    ui.label("Sensors").classes("text-lg font-semibold mt-2")
                    with ui.column().classes("gap-2"):
                        ui.label(
                            "Select which sensors should belong to this device. Only sensors that are not yet assigned to a device are allowed.")
                        sensors = Sensor.get_all_unassigned()
                        sensors.extend(self.device.sensors)
                        sensors.sort(key=lambda x: x.id)

                        sensor_options = {
                            sensor.id: sensor.name for sensor in sensors}
                        preselected = [sensor.id for sensor in self.device.sensors]

                        with ui.row().classes("items-center"):
                            self.sensor_select = ui.select(
                                options=sensor_options, multiple=True, value=preselected).props('use-chips').classes("w-[130px] max-w-[350px]")
                            ui.button("Save", on_click=self.change_sensors).props(
                                "flat")

    def copy_to_clipboard(self, text):
        '''Copies the given text to the clipboard'''
        pyperclip.copy(text)
        ui.notify("Copied to clipboard.")

    def change_container(self):
        '''Changes the container of the device'''

        # Check if container is active
        if self._check_if_container_is_active(self.device.container):
            return

        # Check if new container is active
        new_container_id = self.container_select.value
        new_container = Container.get_by_id(new_container_id)
        if self._check_if_container_is_active(new_container):
            return
        
        self.device.container_id = new_container_id
        Container.session.commit()

        self.container_label.text = new_container.name
        ui.notify(f"Changes saved successfully.", type="positive")

    def change_sensors(self):
        '''Changes the sensors of the device'''

        # Check if container is active
        if self._check_if_container_is_active(self.device.container):
            return
        
        self.device.clear_relationship_to_sensors()
        self.device.create_relationship_to_sensors(self.sensor_select.value)

        self.sensor_count_label.text = f'{len(self.device.sensors)}'
        ui.notify(f"Changes saved successfully.", type="positive")

    def _check_if_container_is_active(self, container):
        '''Checks if the given container is active and shows a warning if it is'''
        if container is not None and container.is_active:
            ui.notify(
                f"Changes cannot be applied while container '{container.name}' is active.", type="warning")
            return True
        return False
