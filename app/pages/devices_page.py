from nicegui import ui
from models.device import Device
from models.sensor import Sensor
from components.device_item import DeviceItem


class DevicesPage:
    '''This class represents the devices page.'''

    def __init__(self, iot_hub_helper):
        '''Initializes the page'''
        self.iot_hub_helper = iot_hub_helper
        self.devices = []
        self.list_items = []
        self.list_container = None
        self.devices_count = 0

    def create_page(self):
        """Create the devices page"""
        self.update_stats()  # Move database query here
        self.setup_layout()
        self.setup_menu_bar()
        self.setup_list()

    def setup_layout(self):
        '''Sets up Navigation and updates page title'''
        ui.query('.nicegui-content').classes('mx-auto max-w-screen-2xl p-8')
        ui.label("Devices").classes('text-2xl font-bold')

    def setup_menu_bar(self):
        '''Sets up the menu bar'''
        with ui.row().classes('p-4 w-full flex items-center justify-between bg-gray-200 rounded-lg shadow-md'):
            # Create new device
            ui.button('Create New Device',
                      on_click=lambda: self.show_create_device_dialog()).classes('')

            # Stats
            with ui.row().classes('gap-1'):
                ui.label('Total:').classes('text-sm font-medium')
                ui.label().classes('text-sm').bind_text(self, 'devices_count')

            # Filter
            with ui.row():
                self.filter_input = ui.input(
                    placeholder='Filter', on_change=self.filter_handler).classes('w-44')

    def setup_list(self):
        '''Sets up the list of devices'''
        try:
            # Create a new container for the list
            if self.list_container is not None:
                try:
                    self.list_container.delete()
                except Exception as e:
                    print(f"Error removing old list container: {str(e)}")

            self.list_container = ui.column().classes('relative w-full min-w-[600px] gap-0 divide-y')

            with self.list_container:
                # Add headings row
                headings = [{'name': 'ID', 'classes': 'w-[30px]'},
                            {'name': 'Name', 'classes': 'w-[130px]'},
                            {'name': 'Container', 'classes': 'w-[130px]'},
                            {'name': 'Sensors', 'classes': 'w-[60px]'}]

                with ui.row().classes('px-3 py-6 flex gap-6 items-center w-full'):
                    for heading in headings:
                        ui.label(heading['name']).classes(
                            f'font-medium {heading["classes"]}')

                self.setup_note_label()

                # Print list items
                self.refresh_device_list()
        except Exception as e:
            print(f"Error setting up list: {str(e)}")

    def refresh_device_list(self):
        """Refresh the list of devices"""
        try:
            # Clear existing items by removing their parent containers
            for item in self.list_items:
                if hasattr(item, 'item') and item.item is not None:
                    try:
                        if hasattr(item.item, 'parent') and item.item.parent is not None:
                            item.item.parent.delete()
                        else:
                            item.item.delete()
                    except Exception as e:
                        print(f"Error removing item container: {str(e)}")

            # Clear the list
            self.list_items.clear()

            # Get updated devices
            self.devices = Device.get_all()

            # Show note if no devices
            if len(self.devices) == 0:
                self.show_note('No devices available')
                return

            # Hide note and add devices
            if hasattr(self, 'note_label'):
                self.note_label.set_visibility(False)

            # Create new items within the list container
            if self.list_container is not None and self.list_container.client:
                with self.list_container:
                    for device in self.devices:
                        try:
                            new_item = DeviceItem(device=device,
                                                delete_callback=self.delete_button_handler)
                            self.list_items.append(new_item)
                        except Exception as e:
                            print(f"Error creating device item: {str(e)}")

        except Exception as e:
            print(f"Error refreshing device list: {str(e)}")
            if hasattr(self, 'note_label'):
                self.show_note('Error loading devices')

    def setup_note_label(self):
        '''Sets up the note label'''
        with self.list_container:
            self.note_label = ui.label().classes(
                'absolute left-1/2 top-48 self-center -translate-x-1/2 !border-t-0')
            self.note_label.set_visibility(False)

    def show_note(self, text):
        '''Shows a note in the list'''
        if hasattr(self, 'note_label') and self.note_label is not None:
            self.note_label.set_text(text)
            self.note_label.set_visibility(True)

    def update_stats(self):
        '''Updates the stats'''
        try:
            self.devices = Device.get_all()
            self.devices_count = len(self.devices)
        except Exception as e:
            print(f"Error updating stats: {str(e)}")
            self.devices_count = 0

    def filter_handler(self, e):
        '''Handles the filter input'''
        try:
            filter_text = e.value.lower()
            for item in self.list_items:
                if hasattr(item, 'device') and item.device is not None:
                    item.visible = filter_text in item.device.name.lower()
        except Exception as e:
            print(f"Error handling filter: {str(e)}")

    def delete_button_handler(self, device):
        '''Handles the delete button click'''
        try:
            with ui.dialog() as dialog, ui.card():
                ui.label('Are you sure you want to delete this device?')
                with ui.row():
                    ui.button('Cancel', on_click=dialog.close).props('flat')
                    ui.button('Delete', on_click=lambda d=dialog: self.delete_handler(
                        d, device)).props('flat color=red')
        except Exception as e:
            print(f"Error showing delete dialog: {str(e)}")

    def delete_handler(self, dialog, device):
        '''Handles the device deletion'''
        try:
            # Delete the device from the database
            device.delete()
            dialog.close()
            
            # Refresh the device list
            self.refresh_device_list()
            self.update_stats()
        except Exception as e:
            print(f"Error deleting device: {str(e)}")
            dialog.close()

    def show_create_device_dialog(self):
        '''Shows the create device dialog'''
        try:
            with ui.dialog(value=True) as dialog, ui.card().classes('relative w-[696px] min-h-[500px]'):
                ui.button(icon="close", on_click=dialog.close).props(
                        "flat").classes("absolute top-6 right-6 px-2 text-black z-10")

                with ui.stepper().props('vertical') as stepper:
                    # General values
                    with ui.step('General'):
                        ui.label('Specifies the name of the device. The device can then be found in the IoT Hub with this name.')
                        name_input = ui.input('Name*')
                        with ui.stepper_navigation():
                            ui.button('Cancel', on_click=lambda: dialog.close()).props('flat')
                            ui.button('Next', on_click=lambda: self.check_general_step_input(stepper, name_input))
                    with ui.step('Sensors'):
                        sensors = Sensor.get_all_unassigned()
                        if len(sensors) > 0:
                            ui.label('Select the sensors to be assigned to the device. Multiple selection possible.')
                            sensor_options = {sensor.id: sensor.name for sensor in sensors}
                            sensor_select = ui.select(options=sensor_options, multiple=True).classes('w-40')
                        else:
                            ui.label('No sensors available yet. You can switch to the Sensors page, create sensors and then add them to this device.')
                        with ui.stepper_navigation():
                            ui.button('Back', on_click=stepper.previous).props('flat')
                            ui.button('Create', on_click=lambda: self.create_device(dialog, name_input, sensor_select))
        except Exception as e:
            print(f"Error showing create dialog: {str(e)}")

    def check_general_step_input(self, stepper, name_input):
        '''Checks the input of the general step'''
        try:
            if not name_input.value:
                ui.notify('Please enter a name for the device')
                return

            if Device.check_if_name_in_use(name_input.value):
                ui.notify('A device with this name already exists')
                return

            stepper.next()
        except Exception as e:
            print(f"Error checking general step input: {str(e)}")
            ui.notify('Error checking device name')

    def create_device(self, dialog, name_input, sensor_select):
        '''Creates a new device'''
        try:
            # Create device
            device = Device.add(device_name=name_input.value)
            
            # Add selected sensors
            if hasattr(sensor_select, 'value') and sensor_select.value:
                for sensor_id in sensor_select.value:
                    sensor = Sensor.get_by_id(sensor_id)
                    if sensor:
                        sensor.device_id = device.id
                        sensor.save()

            dialog.close()
            self.refresh_device_list()
            self.update_stats()
            ui.notify('Device created successfully')
        except Exception as e:
            print(f"Error creating device: {str(e)}")
            ui.notify('Error creating device')
