from nicegui import ui
from src.models.device import Device
from src.components.logs_dialog import LogsDialog
from src.components.sensor_selection import SensorSelection
from src.components.chart import Chart
from src.utils.iot_hub_helper import IoTHubHelper
from src.utils.mqtt_helper import MQTTHelper
from src.utils.export_helper import ExportHelper
from loguru import logger
import asyncio


class ContainerCard():
    '''Container card component for displaying container information'''

    def __init__(self, wrapper, container, start_callback=None, stop_callback=None, delete_callback=None, live_view_callback=None):
        '''Initializes the container card'''
        self.wrapper = wrapper
        self.container = container
        self.card = None
        self.visible = True
        self.sensor_count = 0
        self.generated_container_data = None
        self.logs_dialog = LogsDialog(wrapper)
        self.container.log = self.logs_dialog.log
        self.active_dot = None
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.delete_callback = delete_callback
        self.live_view_callback = live_view_callback
        self.setup(wrapper, container)

    def setup(self, wrapper, container):
        '''Sets up initial UI elements of the container card'''
        try:
            with ui.card().tight().bind_visibility(self, 'visible') as card:
                self.card = card
                with ui.card_section().classes('min-h-[260px]'):
                    # Container header
                    with ui.row().classes('pb-2 w-full justify-between items-center border-b border-gray-200'):
                        ui.label(container.name).classes('text-xl font-semibold')
                        with ui.row().classes('gap-0.5'):
                            if self.live_view_callback:
                                ui.button(icon='insert_chart_outlined', on_click=lambda: self.live_view_callback(
                                    container)).props('flat').classes('px-2 text-black')
                            with ui.button(icon='more_vert').props('flat').classes('px-2 text-black'):
                                with ui.menu().props(remove='no-parent-event'):
                                    ui.menu_item('Show Details', lambda: self.show_details_dialog()).classes(
                                        'flex items-center')
                                    ui.menu_item('Show Logs', lambda: self.show_logs_dialog(container)).classes(
                                        'flex items-center')
                                    ui.menu_item('Delete', lambda: self.show_delete_dialog(
                                        wrapper, container)).classes('text-red-500').classes('flex items-center')

                    # Container information
                    with ui.column().classes('py-4 gap-2'):
                        with ui.row().classes('gap-1'):
                            ui.label('Devices:').classes('text-sm font-medium')
                            ui.label().classes('text-sm').bind_text_from(container,
                                                                         'devices', backward=lambda d: len(d))
                        with ui.row().classes('gap-1'):
                            ui.label('Sensors:').classes('text-sm font-medium')
                            self.sensor_count_label = ui.label().classes('text-sm')
                            self.sensor_count_label.bind_text(self, 'sensor_count')
                        with ui.row().classes('gap-1'):
                            ui.label('Messages Sent:').classes(
                                'text-sm font-medium')
                            ui.label().classes('text-sm').bind_text(container, 'message_count')
                        with ui.row().classes('gap-1'):
                            ui.label('Start time:').classes('text-sm font-medium')
                            ui.label().classes('text-sm').bind_text_from(container, 'start_time',
                                                                         backward=lambda t: f'{t.strftime("%d.%m.%Y, %H:%M:%S")} UTC' if t else '')

                # Container controls
                with ui.card_section().classes('bg-gray-100'):
                    with ui.row().classes('items-center justify-between'):
                        with ui.row().classes('gap-3 items-center'):
                            self.active_dot = ui.row().classes('h-4 w-4 rounded-full' +
                                                               (' bg-green-500' if container.is_active else ' bg-red-500'))
                            self.status_label = ui.label().bind_text_from(container, 'is_active',
                                                      backward=lambda is_active: f'{"Active" if is_active else "Inactive"}')
                        with ui.row().classes('h-9 gap-0.5'):
                            with ui.row().classes('gap-0.5'):
                                if self.start_callback:
                                    self.start_button = ui.button(icon='play_arrow', on_click=lambda: self.show_interface_selection_dialog(container, self.start_callback)).props('flat').classes('px-2 text-black')
                                    self.start_button.set_visibility(not container.is_active)
                                if self.stop_callback:
                                    self.stop_button = ui.button(icon='pause', on_click=lambda c=container: self.stop_callback(
                                        c)).props('flat').classes('px-2 text-black')
                                    self.stop_button.set_visibility(container.is_active)
                            ui.row().classes('w-px h-full bg-gray-300')
                            ui.button(icon='exit_to_app', on_click=lambda: self.show_export_dialog()).props('flat').classes('px-2 text-black')

            self.update_sensor_count()
        except Exception as e:
            print(f"Error setting up container card: {str(e)}")

    def set_active(self):
        """Set the container card to active state"""
        try:
            if not self.status_label or not self.status_label.client:
                return
                
            self.status_label.text = "Active"
            self.status_label.classes('text-green-500', remove='text-red-500')
        except Exception as e:
            print(f"Error setting active state: {str(e)}")

    def set_inactive(self):
        """Set the container card to inactive state"""
        try:
            if not self.status_label or not self.status_label.client:
                return
                
            self.status_label.text = "Inactive"
            self.status_label.classes('text-red-500', remove='text-green-500')
        except Exception as e:
            print(f"Error setting inactive state: {str(e)}")

    def update_sensor_count(self):
        """Update the sensor count display"""
        try:
            if not self.sensor_count_label or not self.sensor_count_label.client:
                return
                
            total_sensors = sum(len(device.sensors) for device in self.container.devices)
            self.sensor_count_label.text = str(total_sensors)
        except Exception as e:
            print(f"Error updating sensor count: {str(e)}")

    def show_interface_selection_dialog(self, container, start_callback):
        '''Shows the interface selection dialog, whether to use IoT Hub or MQTT'''
        with self.wrapper:
            with ui.dialog(value=True) as dialog, ui.card().classes("px-6 pb-6 overflow-auto"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label(
                        "Select Interface").classes("text-xl font-semibold")
                    ui.button(icon="close", on_click=dialog.close).props(
                        "flat").classes("px-2 text-black")
                
                with ui.column():
                    ui.label("Choose which interface to use for sending the data.")

                # IoT Hub
                with ui.row().classes("w-full justify-between items-center md:flex-nowrap md:gap-8"):
                    host_name = IoTHubHelper.get_host_name()
                    host_name_is_none = host_name is None
                    host_name = host_name if host_name else 'Not Configured'
                    
                    with ui.column().classes("mt-4 gap-1"):
                        ui.label("IoT Hub").classes("text-sm font-medium")
                        ui.label(f"Hostname: {host_name}")
                        iot_hub_note_label = ui.label().classes("mt-2 py-1 px-2 text-x text-gray-600 bg-gray-100 rounded-md")
                    iot_hub_start_button = ui.button('Start', icon='play_arrow', on_click=lambda: self.start_handler(dialog, start_callback, container, "iothub")).classes('w-28 shrink-0')
                    
                    if host_name_is_none:
                        iot_hub_note_label.text = "Set environment variables to configure (see README.md)"
                        iot_hub_start_button.set_enabled(False)
                    else:
                        iot_hub_note_label.set_visibility(False)

                # Separator
                with ui.row().classes("w-full items-center"):
                    ui.row().classes("h-px grow bg-gray-300")
                    ui.label("or").classes("text-sm font-medium")
                    ui.row().classes("h-px grow bg-gray-300")

                # MQTT
                with ui.row().classes("w-full justify-between items-center md:flex-nowrap md:gap-8"):
                    mqtt_broker_address = MQTTHelper.get_broker_address()
                    mqtt_broker_port = MQTTHelper.get_broker_port()

                    mqtt_broker_address = mqtt_broker_address if mqtt_broker_address else 'Not Configured'
                    mqtt_broker_port = mqtt_broker_port if mqtt_broker_port else 'Not Configured'

                    with ui.column().classes("mt-4 gap-1"):
                        ui.label("MQTT Broker").classes("text-sm font-medium")
                        ui.label(f"Address: {mqtt_broker_address}")
                        ui.label(f"Port: {mqtt_broker_port}")
                    mqtt_start_button = ui.button('Start', icon='play_arrow', on_click=lambda: self.start_handler(dialog, start_callback, container, "mqtt")).classes('w-28 shrink-0')

                    if not MQTTHelper.is_configured():
                        mqtt_start_button.set_enabled(False)

    def start_handler(self, dialog, start_callback, container, interface):
        '''Starts the container and closes the dialog'''
        dialog.close()
        start_callback(container, interface)

    def show_details_dialog(self):
        '''Shows the details dialog'''
        with self.wrapper:
            with ui.dialog(value=True) as dialog, ui.card().classes("px-6 pb-6 w-[696px] !max-w-none overflow-auto"):
                self.dialog = dialog
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label(
                        f"Details - '{self.container.name}'").classes("text-xl font-semibold")
                    ui.button(icon="close", on_click=self.dialog.close).props(
                        "flat").classes("px-2 text-black")

                with ui.row().classes("w-full flex justify-between"):
                    # Container information
                    with ui.column().classes("gap-4"):
                        ui.label("General").classes(
                            "text-lg font-semibold mt-2")
                        with ui.row().classes("grid grid-cols-2 gap-y-4 gap-x-10 sm:flex"):
                            with ui.column().classes("gap-0"):
                                ui.label("ID").classes("text-sm text-gray-500")
                                ui.label(f"{self.container.id}").classes(
                                    "text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Name").classes(
                                    "text-sm text-gray-500")
                                ui.label(f"{self.container.name}").classes(
                                    "text-md font-medium")
                            with ui.column().classes("gap-0"):
                                ui.label("Location").classes(
                                    "text-sm text-gray-500")
                                location = self.container.location
                                ui.label(f"{location if location else 'N/A'}").classes(
                                    "text-md font-medium")
                        with ui.row().classes("gap-10"):
                            with ui.column().classes("gap-0"):
                                ui.label("Description").classes(
                                    "text-sm text-gray-500")
                                description = self.container.description
                                ui.label(f"{description if description else 'N/A'}").classes(
                                    "text-md font-medium")
                                
                    # Container status
                    with ui.column().classes('pr-3 gap-1 items-end'):
                        ui.label("Status").classes("text-sm text-gray-500")
                        with ui.row().classes('gap-3 items-center'):
                            ui.row().classes(
                                f'h-4 w-4 rounded-full {"bg-green-500" if self.container.is_active else "bg-red-500"}')
                            ui.label().bind_text_from(self.container, 'is_active',
                                                      backward=lambda is_active: f'{"Active" if is_active else "Inactive"}')

                # Container and sensors
                with ui.column().classes("w-full gap-4"):
                    ui.label("Devices and Sensors").classes(
                        "text-lg font-semibold mt-2")

                    # Device tree
                    with ui.row().classes("gap-x-28"):
                        with ui.column().classes('gap-0'):
                            ui.label("View").classes(
                                "text-sm text-gray-500")
                            data = self.create_tree_data(
                                self.container.devices)
                            with ui.row() as row:
                                self.tree_container = row
                                ui.tree(
                                    data, label_key="id")

                        # Add device
                        unassigned_devices = Device.get_all_unassigned()
                        with ui.column().classes('gap-0'):
                            device_options = {
                                device.id: device.name for device in unassigned_devices}

                            ui.label("Edit").classes(
                                "text-sm text-gray-500")
                            if len(unassigned_devices) > 0:
                                with ui.row().classes("items-center"):
                                    self.new_device_select = ui.select(
                                        value=unassigned_devices[0].id, options=device_options).classes("min-w-[120px]")
                                    ui.button("Add", on_click=self.add_device_handler).props(
                                        "flat")
                            else:
                                ui.label(
                                    "No more devices available.").classes()

    def create_tree_data(self, devices):
        """Create tree data structure for devices and sensors"""
        try:
            tree_data = []
            for device in devices:
                device_node = {
                    "id": device.name,
                    "children": []
                }
                for sensor in device.sensors:
                    sensor_node = {
                        "id": f"{sensor.name} ({UNITS[sensor.unit]['abbreviation']})"
                    }
                    device_node["children"].append(sensor_node)
                tree_data.append(device_node)
            return tree_data
        except Exception as e:
            print(f"Error creating tree data: {str(e)}")
            return []
    
    def show_export_dialog(self):
        '''Shows the export dialog for exporting bulk data'''
        if len(self.container.devices) == 0:
            ui.notify("No devices available!", type="warning")
            return

        if self.container.is_active:
            ui.notify("Please deactivate the container to perform a bulk export.", type="warning")
            return

        with self.wrapper:
            with ui.dialog(value=True) as dialog, ui.card().classes("relative px-6 pb-6 w-[696px] !max-w-none overflow-auto") as card:
                self.dialog = dialog
                self.bulk_export_card = card
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label(
                        f"Bulk Export - '{self.container.name}'").classes("text-xl font-semibold")
                    ui.button(icon="close", on_click=dialog.close).props(
                        "flat").classes("px-2 text-black")
                
                ui.label("Perform a bulk export and choose how the data should be exported.")

                # Bulk data generation
                with ui.row().classes("gap-6 items-center"):
                    self.bulk_amount_input = ui.number(label="Values per Sensor", min=1, max=1000000, step=1, value=100).classes('w-24')
                    ui.button("Generate Data", on_click=self.generate_bulk_data).props("flat")

                # Visualization
                ui.label("Preview").classes("text-lg font-semibold mt-2")

                self.sensor_selection = SensorSelection(container=self.container, sensor_select_callback=self.update_export_preview)
                self.chart = Chart()

                self.export_button = ui.button("Export", on_click=self.save_bulk_to_file).classes("mt-8 self-end")
                self.export_button.set_enabled(False)

    async def generate_bulk_data(self):
        '''Generates bulk data for the export'''
        bulk_export_spinner = None

        with self.bulk_export_card:
            with ui.row().classes("absolute top-0 left-0 w-full h-full bg-black opacity-20 z-10") as overlay:
                bulk_export_spinner = overlay
                ui.spinner(size='lg').classes("absolute top-1/2 left-1/2 transform -translate-x-full -translate-y-1/2")

        self.chart.show_note("Generating data...", force=True)
        await asyncio.sleep(0.1) # Workaround to make the spinner visible

        container_data = {}
        bulk_amount = int(self.bulk_amount_input.value)

        for device in self.container.devices:
            device_data = {}
            for sensor in device.sensors:
                data = sensor.start_bulk_simulation(bulk_amount)
                device_data[sensor.name] = data
            container_data[device.name] = device_data
        
        self.generated_container_data = container_data

        if bulk_amount <= 1000:
            self.show_export_preview(container_data)
        else:
            self.chart.show_note("Preview not available (more than 1,000 values)", force=True)
        self.export_button.set_enabled(True)

        bulk_export_spinner.clear()
        bulk_export_spinner.set_visibility(False)

    def save_bulk_to_file(self):
        '''Saves the generated bulk data to a file'''
        ExportHelper().save_to_file(self.generated_container_data)
        ui.notify(f"Data exported successfully", type="positive")
        self.dialog.close()

    def show_export_preview(self, container_data):
        '''Shows the export preview chart'''
        selected_sensor = self.sensor_selection.get_sensor()
        time_series_data = container_data[selected_sensor.device.name][selected_sensor.name]
        self.chart.show(time_series_data=time_series_data)

    def update_export_preview(self, sensor):
        '''Updates the export preview chart'''
        if self.generated_container_data is None:
            return
        elif sensor is None:
            self.chart.empty()
            return
        
        time_series_data = self.generated_container_data[sensor.device.name][sensor.name]
        self.chart.update(sensor, time_series_data)

    def add_device_handler(self):
        '''Adds a device to the container'''
        if self.container.is_active:
            ui.notify(
                f"Cannot add while this container is active.", type="negative")
            return

        device_id = self.new_device_select.value
        device = Device.get_by_id(device_id)
        device.container_id = self.container.id
        Device.session.commit()

        ui.notify(f"Device added successfully.", type="positive")
        self.update_sensor_count()

        # Remove device from select
        del self.new_device_select.options[device_id]
        self.new_device_select.update()
        self.new_device_select.value = None

        # Show device in tree
        new_data = self.create_tree_data(self.container.devices)
        self.tree_container.clear()
        with self.tree_container:
            ui.tree(new_data, label_key="id")

    def show_logs_dialog(self, container):
        '''Shows the logs dialog'''
        if not container.is_active:
            ui.notify('Container is not active', type='warning')
            return

        self.logs_dialog.show()

    def show_delete_dialog(self, wrapper, container):
        '''Shows the delete dialog'''
        try:
            with wrapper:
                with ui.dialog(value=True) as dialog, ui.card().classes('items-center'):
                    ui.label('Do you want to delete this container?')
                    with ui.row():
                        ui.button('Cancel', on_click=dialog.close).props('flat')
                        ui.button('Delete', on_click=lambda: self.delete_handler(
                            dialog)).classes('text-white bg-red')
        except Exception as e:
            print(f"Error showing delete dialog: {str(e)}")

    def delete_handler(self, dialog):
        """Handle the deletion of the container"""
        try:
            # Call the delete callback if provided
            if self.delete_callback:
                self.delete_callback(self.container, dialog)
                return
                
            # If no callback, handle deletion here
            # Close the dialog first
            dialog.close()
            
            # Stop the container if it's active
            if self.container.is_active:
                self.container.stop()
            
            # Delete the container from the database
            self.container.delete()
            
            # Clean up UI elements
            if hasattr(self, 'card') and self.card is not None:
                try:
                    self.card.delete()
                except Exception as e:
                    print(f"Error cleaning up container card UI: {str(e)}")
                
        except Exception as e:
            print(f"Error deleting container card: {str(e)}")
            ui.notify("Error deleting container", type="error")

    def update_tree(self):
        """Update the device tree"""
        try:
            if not self.tree_container or not self.tree_container.client:
                return
                
            self.tree_container.clear()
            with self.tree_container:
                new_data = self.create_tree_data(self.container.devices)
                ui.tree(new_data, label_key="id")
        except Exception as e:
            print(f"Error updating tree: {str(e)}")

    def update_ui(self):
        """Update the UI elements to reflect the current state of the container"""
        try:
            # Update the status indicator
            if self.active_dot:
                self.active_dot.classes(remove=['bg-red-500', 'bg-green-500'])
                self.active_dot.classes('bg-green-500' if self.container.is_active else 'bg-red-500')
            
            # Update the status label
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.set_text('Active' if self.container.is_active else 'Inactive')
                
            # Update the start/stop buttons if they exist
            if hasattr(self, 'start_button') and self.start_button:
                self.start_button.set_visibility(not self.container.is_active)
                
            if hasattr(self, 'stop_button') and self.stop_button:
                self.stop_button.set_visibility(self.container.is_active)
                
            logger.debug(f"Updated UI for container {self.container.name}, active status: {self.container.is_active}")
        except Exception as e:
            logger.error(f"Error updating container card UI: {str(e)}")
