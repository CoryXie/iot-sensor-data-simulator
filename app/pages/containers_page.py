from nicegui import ui
from models.container import Container
from models.device import Device
from models.sensor import Sensor
from components.navigation import Navigation
from components.container_card import ContainerCard
from components.live_view_dialog import LiveViewDialog
from utils.iot_hub_helper import IoTHubHelper


class ContainersPage:
    '''This class represents the containers page.'''

    def __init__(self, iot_hub_helper):
        self.iot_hub_helper = iot_hub_helper
        self.containers = []
        self.cards_grid = None
        self.cards = []
        self.containers_count = 0
        self.active_containers_count = 0
        self.inactive_containers_count = 0

    def create_page(self):
        """Create the containers page"""
        self.update_stats()  # Move database query here
        self.setup_layout()
        self.setup_menu_bar()
        self.setup_cards_grid()
        self.setup_live_view_dialog()

    def setup_layout(self):
        '''Sets up Navigation and updates page title'''
        ui.query('main').classes('h-px')
        ui.query('.nicegui-content').classes('mx-auto max-w-screen-2xl p-8')
        ui.label("Container").classes('text-2xl font-bold')

    def setup_menu_bar(self):
        '''Sets up the menu bar'''
        with ui.row().classes('p-4 w-full flex items-center justify-between bg-gray-200 rounded-lg shadow-md'):
            # Create container button
            ui.button('Create New Container',
                      on_click=lambda: self.open_create_container_dialog()).classes('')

            # Container stats
            with ui.row():
                with ui.row().classes('gap-1'):
                    ui.label('Total:').classes('text-sm font-medium')
                    ui.label().classes('text-sm').bind_text(self, 'containers_count')
                with ui.row().classes('gap-1'):
                    ui.label('Active:').classes('text-sm font-medium')
                    ui.label().classes('text-sm').bind_text(self, 'active_containers_count')
                with ui.row().classes('gap-1'):
                    ui.label('Inactive:').classes('text-sm font-medium')
                    ui.label().classes('text-sm').bind_text(self, 'inactive_containers_count')

            # Filter
            with ui.row():
                self.filter_input = ui.input(
                    placeholder='Filter', on_change=self.filter_handler).classes('w-44')
                self.filter_state_select = ui.select({1: "All", 2: "Active", 3: "Inactive"},
                          value=1, on_change=self.filter_handler).classes('w-24')

    def setup_cards_grid(self):
        """Setup the container cards grid"""
        try:
            self.cards_grid = ui.grid(columns=3).classes('gap-4 p-4')
            
            if not self.containers:
                with self.cards_grid:
                    ui.label('No containers available').classes('text-gray-500')
                return
            
            for container in self.containers:
                with self.cards_grid:
                    card = ContainerCard(
                        wrapper=self.cards_grid,
                        container=container,
                        start_callback=self.start_container,
                        stop_callback=self.stop_container,
                        delete_callback=self.delete_container,
                        live_view_callback=self.show_live_view_dialog
                    )
                    self.cards.append(card)
        except Exception as e:
            print(f"Error setting up cards grid: {str(e)}")

    def setup_note_label(self):
        '''Sets up the note label, which is shown when no containers are available for instance'''
        with self.cards_grid:
            self.note_label = ui.label().classes(
                'absolute left-1/2 top-48 self-center -translate-x-1/2')
            self.note_label.set_visibility(False)

    def setup_live_view_dialog(self):
        '''Sets up the live view dialog. There is only one instance of the dialog, which is reused for every container.'''
        self.live_view_dialog = LiveViewDialog(self.cards_grid)

        for container in self.containers:
            container.live_view_dialog = self.live_view_dialog

    def update_stats(self):
        """Update container statistics"""
        try:
            # Refresh containers list
            self.containers = Container.get_all()
            
            # Update counts
            self.containers_count = len(self.containers)
            self.active_containers_count = sum(1 for c in self.containers if c.is_active)
            self.inactive_containers_count = self.containers_count - self.active_containers_count
        except Exception as e:
            print(f"Error updating stats: {str(e)}")

    def filter_handler(self, e=None):
        """Handle container filtering"""
        try:
            filter_text = self.filter_input.value.lower() if self.filter_input.value else ""
            filter_state = self.filter_state_select.value
            
            for card in self.cards:
                if not card.card or not card.card.client:
                    continue
                    
                container = card.container
                name_match = filter_text in container.name.lower()
                state_match = (filter_state == 1 or 
                             (filter_state == 2 and container.is_active) or 
                             (filter_state == 3 and not container.is_active))
                
                card.card.classes('hidden', remove=True) if name_match and state_match else card.card.classes('hidden', add=True)
        except Exception as e:
            print(f"Error handling filter: {str(e)}")

    def show_note(self, message):
        '''Shows the note label with the given message'''
        self.cards_grid.classes('justify-center')
        self.note_label.text = message
        self.note_label.set_visibility(True)

    def hide_note(self):
        '''Hides the note label'''
        self.cards_grid.classes('justify-start')
        self.note_label.set_visibility(False)

    def open_create_container_dialog(self):
        '''Opens the create container dialog'''
        with ui.dialog(value=True) as dialog, ui.card().classes('w-[696px] min-h-[500px]'):
            ui.button(icon="close", on_click=dialog.close).props(
                "flat").classes("absolute top-6 right-6 px-2 text-black z-10")

            with ui.stepper().classes('w-full').props('vertical') as stepper:
                with ui.step('General'):
                    with ui.column():
                        name_input = ui.input('Name*')
                        description_textarea = ui.textarea(
                            label='Description (max. 255 characters)', validation={'Maximum 255 characters allowed!': lambda value: len(value) < 256}).classes('w-full')
                        location_input = ui.input('Location').classes('w-full')
                    with ui.stepper_navigation():
                        ui.button('Cancel', on_click=lambda: dialog.close()).props(
                            'flat')
                        ui.button('Next', on_click=lambda: self.check_container_general_input(
                            stepper, name_input, description_textarea))
                with ui.step('Devices'):
                    devices = Device.get_all_unassigned()
                        
                    devices_options = {
                        device.id: device.name for device in devices}

                    if len(devices) == 0:
                        ui.label(
                            "No devices available.")
                    else:
                        ui.label(
                            "Select the devices to be assigned to the container. Multiple selection possible.")
                    devices_input = ui.select(devices_options, multiple=True, label='Select devices').props(
                        'use-chips').classes('sm:w-64')

                    with ui.stepper_navigation():
                        ui.button('Back', on_click=stepper.previous).props(
                            'flat')
                        ui.button('Create', on_click=lambda: self.complete_container_creation(
                            dialog, name_input, description_textarea, location_input, devices_input))

    def check_container_general_input(self, stepper, name_input, description_textarea):
        '''Checks the general input of the create container dialog'''

        # Check if name is empty
        if name_input.value == '':
            ui.notify('Please enter a name.',
                      type='negative')
            return
        # Check if name is already in use
        else:
            name_in_use = Container.check_if_name_in_use(name_input.value)
            if name_in_use:
                ui.notify('A container with this name already exists.', type='negative')
                return
        
        # Check if description is too long
        if len(description_textarea.value) > 255:
            ui.notify('Description must not exceed 255 characters.',
                      type='negative')
            return

        stepper.next()

    def complete_container_creation(self, dialog, name_input, description_textarea, location_input, devices_input):
        '''Completes the container creation'''
        self.create_container(name_input.value, description_textarea.value,
                              location_input.value, devices_input.value)
        
        ui.notify('Container created successfully.', type='positive')
        dialog.close()

    def create_container(self, name, description, location, device_ids):
        '''Creates a new container'''
        if len(self.containers) == 0:
            self.cards_grid.clear()
            self.note_label.set_visibility(False)

        new_container = Container.add(
            name, description, location, device_ids)
        new_container.live_view_dialog = self.live_view_dialog
        self.containers.append(new_container)
        with self.cards_grid:
            new_container_card = ContainerCard(
                wrapper=self.cards_grid,
                container=new_container,
                start_callback=self.start_container,
                stop_callback=self.stop_container,
                delete_callback=self.delete_container,
                live_view_callback=self.show_live_view_dialog
            )
            self.cards.append(new_container_card)
        self.update_stats()

    def start_container(self, container, interface):
        """Start container simulation"""
        try:
            if not container.devices:
                ui.notify("No devices available!", type="warning")
                return

            container.start(interface)
            
            # Update UI
            index = next((i for i, card in enumerate(self.cards) if card.container.id == container.id), -1)
            if index >= 0:
                self.cards[index].set_active()
                self.update_stats()
                ui.notify(f"Container {container.name} started successfully", type="positive")
        except Exception as e:
            ui.notify(f"Error starting container: {str(e)}", type="negative")

    def stop_container(self, container):
        """Stop container simulation"""
        try:
            container.stop()
            
            # Update UI
            index = next((i for i, card in enumerate(self.cards) if card.container.id == container.id), -1)
            if index >= 0:
                self.cards[index].set_inactive()
                self.update_stats()
                ui.notify(f"Container {container.name} stopped successfully", type="positive")
        except Exception as e:
            ui.notify(f"Error stopping container: {str(e)}", type="negative")

    def delete_container(self, container, dialog):
        """Delete a container"""
        try:
            # Find the index of the container card
            index = next((i for i, card in enumerate(self.cards) if card.container.id == container.id), -1)
            if index >= 0:
                # Delete the container from the database
                container.delete()
                
                # Delete the card UI element
                self.cards[index].delete()
                
                # Remove from our list
                self.cards.pop(index)
                
                # Update stats
                self.update_stats()
                
                # Close dialog
                dialog.close()
                
                ui.notify(f'Container {container.name} deleted successfully')
            else:
                ui.notify('Container not found', type='warning')
                
        except Exception as e:
            ui.notify(f'Error deleting container: {str(e)}', type='negative')

    def show_live_view_dialog(self, container):
        '''Shows the live view dialog'''
        if len(container.devices) == 0:
            ui.notify("No devices available!", type="warning")
            return

        self.live_view_dialog.show(container)
