from nicegui import ui
from models.device import Device
from models.sensor import Sensor
from constants.units import UNITS
from constants.sensor_errors import *
from components.sensor_error_cards import AnomalyCard, MCARCard, DuplicateDataCard, DriftCard
from components.sensor_item import SensorItem

DEFAULT_BASE_VALUE = 25.00
DEFAULT_VARIATION_RANGE = 5.00
DEFAULT_CHANGE_RATE = 0.5
DEFAULT_INTERVAL = 2

class SensorsPage():
    '''This class represents the sensors page.'''

    def __init__(self):
        '''Initializes the page'''
        self.sensors = []
        self.list_items = []
        self.sensor_error_card = None
        self.sensors_count = 0

    def create_page(self):
        """Create the sensors page"""
        self.update_stats()  # Move database query here
        self.setup_layout()
        self.setup_menu_bar()
        self.setup_list()

    def setup_layout(self):
        '''Sets up Navigation and updates page title'''
        ui.query('.nicegui-content').classes('mx-auto max-w-screen-2xl p-8')
        ui.label("Sensors").classes('text-2xl font-bold')

    def setup_menu_bar(self):
        '''Setup the menu bar'''
        with ui.row().classes('p-4 w-full flex items-center justify-between bg-gray-200 rounded-lg shadow-md'):
            # New sensor button
            ui.button('Create New Sensor',
                      on_click=lambda: self.show_create_sensor_dialog()).classes('')

            # Stats
            with ui.row().classes('gap-1'):
                ui.label('Total:').classes('text-sm font-medium')
                ui.label().classes('text-sm').bind_text(self, 'sensors_count')

            # Filter
            with ui.row():
                self.filter_input = ui.input(
                    placeholder='Filter', on_change=self.filter_handler).classes('w-44')

    def setup_list(self):
        '''Setup the list'''
        self.list_container = ui.column().classes(
            'relative grid w-full min-w-[800px] gap-0 divide-y')

        with self.list_container:
            # Add headings row
            headings = [{'name': 'ID', 'classes': 'w-[30px]'},
                        {'name': 'Name', 'classes': 'w-[130px]'},
                        {'name': 'Type', 'classes': 'w-[130px]'},
                        {'name': 'Device', 'classes': 'w-[130px]'},
                        {'name': 'Error Type', 'classes': 'w-[130px]'}]

            with ui.row().classes('px-3 py-6 flex gap-6 items-center w-full'):
                for heading in headings:
                    ui.label(heading['name']).classes(
                        f'font-medium {heading["classes"]}')
                    
            self.setup_note_label()

            # Print list items
            if len(self.sensors) == 0:
                self.show_note('No Sensors available')
            else:
                for sensor in self.sensors:
                    new_item = SensorItem(sensor=sensor,
                                          delete_callback=self.delete_button_handler)
                    self.list_items.append(new_item)

    def setup_note_label(self):
        '''Setup the note label'''
        with self.list_container:
            self.note_label = ui.label().classes(
                'absolute left-1/2 top-48 self-center -translate-x-1/2 !border-t-0')
            self.note_label.set_visibility(False)

    def filter_handler(self):
        '''Filter the list'''
        search_text = self.filter_input.value
        results = list(filter(lambda item: search_text.lower()
                       in item.sensor.name.lower(), self.list_items))

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
        '''Update the stats'''
        self.sensors = Sensor.get_all()  # Get all sensors from database
        self.sensors_count = len(self.sensors)

    def show_create_sensor_dialog(self):
        '''Show the create sensor dialog'''
        self.sensor_error_card = None
        device_select = None

        with ui.dialog(value=True) as dialog, ui.card().classes("relative w-[696px] !max-w-none"):
                ui.button(icon="close", on_click=dialog.close).props(
                    "flat").classes("absolute top-6 right-6 px-2 text-black z-10")

                with ui.stepper().props('vertical').classes('') as stepper:
                    # General values
                    with ui.step('General'):
                        with ui.grid().classes('sm:grid-cols-2'):
                            name_input = ui.input('Name*')

                            units = {}
                            for index, unit in enumerate(UNITS):
                                units[index] = f"{unit['name']} [{unit['unit_abbreviation']}]"

                            unit_input = ui.select(units, value=0, label='Unit')
                        with ui.stepper_navigation():
                            ui.button('Cancel', on_click=lambda: dialog.close()).props(
                                'flat')
                            ui.button('Next', on_click=lambda: self.check_general_step_input(
                                stepper, name_input))
                    # Simulation values 
                    with ui.step('Simulation Values'):
                        with ui.grid().classes('w-full sm:grid-cols-3'):
                            base_value_input = ui.number(
                                label='Base Value', value=DEFAULT_BASE_VALUE, format='%.2f')
                            variation_range_input = ui.number(label='Variation Range',
                                                            value=DEFAULT_VARIATION_RANGE, min=0, format='%.2f')
                            with ui.number(label='Max. Change Rate +/-', value=DEFAULT_CHANGE_RATE, min=0, max=10) as input:
                                change_rate_input = input
                                ui.tooltip(
                                    'The maximum change rate indicates how much a value can change per interval relative to the previous value.').classes('mx-4')
                            interval_input = ui.number(
                                label='Interval [s]', value=DEFAULT_INTERVAL, min=0, max=3600)
                        with ui.stepper_navigation():
                            ui.button('Back', on_click=stepper.previous).props(
                                'flat')
                            ui.button('Next', on_click=stepper.next)
                    # Error simulation values
                    with ui.step('Error Simulation'):
                        ui.label(
                            'Simulate errors that can occur during measurement.')

                        error_types = {
                            NO_ERROR: 'No Error',
                            ANOMALY: 'Anomalies',
                            MCAR: 'Missing Completely At Random (MCAR)',
                            DUPLICATE_DATA: 'Duplicate Data',
                            DRIFT: 'Drift',
                        }

                        error_container = ui.row()
                        error_type_select = ui.select(options=error_types, value=NO_ERROR, label='Error Type')
                        error_type_select.on('change', lambda e: self.error_type_input_handler(error_container, e.value))

                        with ui.stepper_navigation():
                            ui.button('Back', on_click=stepper.previous).props('flat')
                            ui.button('Next', on_click=stepper.next)
                    # Device assignment
                    with ui.step('Device Assignment'):
                        devices = Device.get_all()
                        devices_options = {
                            device.id: device.name for device in devices}
                        if len(devices) > 0:
                            with ui.column():
                                ui.label(
                                    'Select the device to which this sensor should be assigned (optional).')
                                device_select = ui.select(
                                    options=devices_options, with_input=True).classes('w-40')
                        else:
                            ui.label(
                                'No devices available yet. You can switch to the Devices page, create a device and then add this sensor.')
                        with ui.stepper_navigation():
                            ui.button('Back', on_click=stepper.previous).props(
                                'flat')
                            ui.button('Create', on_click=lambda: self.create_sensor(
                                dialog, name_input, unit_input, base_value_input,
                                variation_range_input, change_rate_input,
                                interval_input, device_select))
                    # Finish
                    with ui.step('Finish'):
                        ui.label(
                            'Create a new sensor with the specified values.')
                        with ui.stepper_navigation():
                            ui.button('Back', on_click=stepper.previous).props(
                                'flat')
                            ui.button('Create', on_click=lambda: self.create_sensor(
                                dialog, name_input, unit_input, base_value_input, variation_range_input, change_rate_input, interval_input, device_select))

    def error_type_input_handler(self, container, value):
        '''Handle the error type. Updates the input container with the corresponding error card.'''

        container.clear()

        if value == NO_ERROR:
            self.sensor_error_card = None
            return
        
        with container:
            if value == ANOMALY:
                self.sensor_error_card = AnomalyCard()
            elif value == MCAR:
                self.sensor_error_card = MCARCard()
            elif value == DUPLICATE_DATA:
                self.sensor_error_card = DuplicateDataCard()
            elif value == DRIFT:
                self.sensor_error_card = DriftCard()

    def check_general_step_input(self, stepper, name_input):
        '''Check the general step input'''

        # Check if name is empty
        if name_input.value == '':
            ui.notify('Please enter a name.',
                      type='negative')
            return
        # Check if name is already in use
        else:
            name_in_use = Sensor.check_if_name_in_use(name_input.value)
            if name_in_use:
                ui.notify('A sensor with this name already exists.', type='negative')
                return

        stepper.next()

    def create_sensor(self, dialog, name_input, unit_input, base_value_input, variation_range_input, change_rate_input, interval_input, device_select):
        '''Create a new sensor'''
        if len(self.sensors) == 0:
            self.hide_note()

        # Read values from inputs
        name = name_input.value
        unit = unit_input.value
        base_value = base_value_input.value
        variation_range = variation_range_input.value
        change_rate = change_rate_input.value
        interval = interval_input.value
        error_definition = None if self.sensor_error_card is None else self.sensor_error_card.get_values(
            json_dump=True)
        device_id = None if device_select is None else device_select.value

        # Create sensor
        new_sensor = Sensor.add(name=name, base_value=base_value, unit=unit, variation_range=variation_range,
                                change_rate=change_rate, interval=interval, error_definition=error_definition, device_id=device_id)
        self.sensors.append(new_sensor)

        # Add to list
        with self.list_container:
            new_item = SensorItem(sensor=new_sensor,
                                  delete_callback=self.delete_button_handler)
            self.list_items.append(new_item)

        dialog.close()
        ui.notify(f"Sensor '{name}' created successfully", type="positive")

        self.update_stats()

    def delete_button_handler(self, sensor):
        '''Handles the delete button click. Opens a dialog to confirm the deletion of the device'''
        with ui.dialog(value=True) as dialog, ui.card().classes('items-center'):
            ui.label(
                f"Do you want to delete the sensor '{sensor.name}'?")
            with ui.row():
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Delete', on_click=lambda d=dialog: self.delete_handler(
                    d, sensor)).classes('text-white bg-red')

    def delete_handler(self, dialog, sensor):
        '''Handles the deletion of a sensor. Deletes the sensor from the database and updates the list'''
        dialog.close()

        # Check if container is active
        if sensor.device is not None and sensor.device.container is not None and sensor.device.container.is_active:
            ui.notify(
                f"Cannot delete while container '{sensor.device.container.name}' is active", type="warning")
            return

        sensor.delete()

        index = self.sensors.index(sensor)
        # Increment due to headings row
        self.list_container.remove(self.list_items[index].item)
        del self.sensors[index]
        del self.list_items[index]

        ui.notify(
            f"Sensor '{sensor.name}' deleted successfully", type="positive")
        self.update_stats()

        if len(self.sensors) == 0:
            self.show_note('No Sensors available')
