from nicegui import ui
from components.navigation import Navigation
from model.device import Device
from model.sensor import Sensor
from components.device_item import DeviceItem


class DevicesPage:
    '''This class represents the devices page.'''

    def __init__(self, iot_hub_helper):
        '''Initializes the page'''
        self.iot_hub_helper = iot_hub_helper
        self.devices = Device.get_all()
        self.list_items = []
        self.update_stats()
        self.setup_page()

    def setup_page(self):
        '''Sets up the page'''
        Navigation()
        ui.query('.nicegui-content').classes('mx-auto max-w-screen-2xl p-8')
        ui.label("Devices").classes('text-2xl font-bold')

        self.setup_menu_bar()
        self.setup_list()

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
            if len(self.devices) == 0:
                self.show_note('No devices available')
            else:
                for device in self.devices:
                    new_item = DeviceItem(device=device,
                                          delete_callback=self.delete_button_handler)
                    self.list_items.append(new_item)

    def setup_note_label(self):
        '''Sets up the note label'''
        with self.list_container:
            self.note_label = ui.label().classes(
                'absolute left-1/2 top-48 self-center -translate-x-1/2 !border-t-0')
            self.note_label.set_visibility(False)

    def filter_handler(self):
        '''Handles the filter input'''
        search_text = self.filter_input.value
        results = list(filter(lambda item: search_text.lower()
                       in item.device.name.lower(), self.list_items))

        for item in self.list_items:
            item.visible = item in results

        if len(results) == 0:
            self.show_note('No matches')
        else:
            self.hide_note()

        if len(results) == 1:
            self.list_container.classes(add='divide-y-0', remove='divide-y')
        else:
            self.list_container.classes(add='divide-y', remove='divide-y-0')

    def show_note(self, message):
        '''Show a note'''
        self.list_container.classes(add='divide-y-0', remove='divide-y')
        self.note_label.text = message
        self.note_label.set_visibility(True)

    def hide_note(self):
        '''Hide the note'''
        self.list_container.classes(add='divide-y', remove='divide-y-0')
        self.note_label.set_visibility(False)

    def update_stats(self):
        '''Updates the stats'''
        self.devices_count = len(self.devices)

    def show_create_device_dialog(self):
        '''Shows the create device dialog'''
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

    def check_general_step_input(self, stepper, name_input):
        '''Check the general step input'''
        # Check if name is empty
        if name_input.value == '':
            ui.notify('Please enter a name.', type='negative')
            return
        # Check if name is already in use
        else:
            name_in_use = Device.check_if_name_in_use(name_input.value)
            if name_in_use:
                ui.notify('A device with this name already exists.', type='negative')
                return

        stepper.next()

    def create_device(self, dialog, name_input, sensor_select):
        '''Create a new device'''
        if len(self.devices) == 0:
            self.hide_note()

        # Read values from inputs
        name = name_input.value
        sensor_ids = sensor_select.value if sensor_select is not None else []

        # Create device
        new_device = Device.add(sensor_ids=sensor_ids, device_name=name)
        if new_device is None:
            ui.notify("Failed to create device", type="negative")
            return

        self.devices.append(new_device)

        # Add to list
        with self.list_container:
            new_item = DeviceItem(device=new_device,
                                delete_callback=self.delete_button_handler)
            self.list_items.append(new_item)

        dialog.close()
        ui.notify(f"Device '{name}' created successfully", type="positive")

        self.update_stats()

    def delete_button_handler(self, device):
        '''Handles the delete button click. Opens a dialog to confirm the deletion of the device'''
        with ui.dialog(value=True) as dialog, ui.card().classes('items-center'):
            ui.label(f"Do you want to delete the device '{device.name}'?")
            with ui.row():
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Delete', on_click=lambda d=dialog: self.delete_handler(
                    d, device)).classes('text-white bg-red')

    def delete_handler(self, dialog, device):
        '''Handles the deletion of a device. Deletes the device from the database and updates the list'''
        dialog.close()

        # Check if container is active
        if device.container is not None and device.container.is_active:
            ui.notify(
                f"Cannot delete while container '{device.container.name}' is active", type="warning")
            return

        device.delete()

        index = self.devices.index(device)
        # Increment due to headings row
        self.list_container.remove(self.list_items[index].item)
        del self.devices[index]
        del self.list_items[index]

        ui.notify(
            f"Device '{device.name}' deleted successfully", type="positive")
        self.update_stats()

        if len(self.devices) == 0:
            self.show_note('No Devices available')

    def replace_special_characters(self, value):
        '''Replaces special characters not allowed in IoT Hub device names'''
        replacements = {
            ' ': '_',
            'Ä': 'AE',
            'Ö': 'OE',
            'Ü': 'UE',
            'ä': 'ae',
            'ö': 'oe',
            'ü': 'ue',
            'ß': 'ss'
        }

        for old_char, new_char in replacements.items():
            value = value.replace(old_char, new_char)

        return value
