from nicegui import ui
from src.models.container import Container
from src.models.device import Device
from src.models.sensor import Sensor
from src.components.navigation import Navigation
from src.components.container_card import ContainerCard
from src.components.live_view_dialog import LiveViewDialog
from src.utils.iot_hub_helper import IoTHubHelper
from src.constants.device_templates import DEVICE_TEMPLATES, SCENARIO_TEMPLATES
from src.database import SessionLocal, db_session
from loguru import logger


class ContainersPage:
    '''This class represents the containers page.'''

    def __init__(self, iot_hub_helper=None):
        self.iot_hub_helper = iot_hub_helper
        logger.info("Initializing ContainersPage")
        self.containers = []
        self.container_templates = []
        self.cards_grid = None
        self.templates_grid = None
        self.cards = []
        self.template_cards = []
        self.containers_count = 0
        self.active_containers_count = 0
        self.inactive_containers_count = 0
        self.templates_count = 0

    def create_page(self):
        """Create the containers page"""
        self.update_stats()  # Move database query here
        self.populate_templates()  # Populate container templates
        self.setup_layout()
        self.setup_menu_bar()
        
        # Setup tabs for different container views
        with ui.tabs().classes('w-full') as tabs:
            ui.tab('Active Containers').classes('text-lg')
            ui.tab('Inactive Containers').classes('text-lg')
            ui.tab('Container Templates').classes('text-lg')
            
        with ui.tab_panels(tabs, value='Active Containers').classes('w-full'):
            with ui.tab_panel('Active Containers'):
                self.setup_cards_grid(active_only=True)
                
            with ui.tab_panel('Inactive Containers'):
                self.setup_cards_grid(active_only=False)
                
            with ui.tab_panel('Container Templates'):
                self.setup_templates_grid()
                
        self.setup_live_view_dialog()

    def setup_layout(self):
        '''Sets up Navigation and updates page title'''
        # Remove any nested header elements
        ui.query('main').classes('h-px')
        ui.query('.nicegui-content').classes('mx-auto max-w-screen-2xl p-8')
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.label("Containers").classes('text-2xl font-bold')

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
                with ui.row().classes('gap-1'):
                    ui.label('Templates:').classes('text-sm font-medium')
                    ui.label().classes('text-sm').bind_text(self, 'templates_count')

            # Filter
            with ui.row():
                self.filter_input = ui.input(
                    placeholder='Filter', on_change=self.filter_handler).classes('w-44')
                self.filter_state_select = ui.select({1: "All", 2: "Active", 3: "Inactive"},
                          value=1, on_change=self.filter_handler).classes('w-24')

    def populate_templates(self):
        """Populate container templates from SCENARIO_TEMPLATES"""
        try:
            self.container_templates = []
            self.templates_count = 0
            
            for scenario_name, scenario in SCENARIO_TEMPLATES.items():
                for container_info in scenario.get('containers', []):
                    room_type = container_info.get('room_type', '')
                    if not room_type:
                        continue
                        
                    template_name = f"{scenario_name} - {room_type.replace('_', ' ').title()}"
                    
                    # Create a pseudo container object for the template
                    template = {
                        'id': f"template_{scenario_name}_{room_type}",
                        'name': template_name,
                        'description': f"{scenario['description']} in {room_type.replace('_', ' ').title()}",
                        'scenario_name': scenario_name,
                        'room_type': room_type,
                        'type': scenario.get('type', 'generic'),
                        'is_template': True,
                        'devices': []
                    }
                    
                    # Add devices from the template
                    for device_info in container_info.get('devices', []):
                        device_type = device_info.get('device_type')
                        if device_type in DEVICE_TEMPLATES:
                            device_template = DEVICE_TEMPLATES[device_type]
                            device = {
                                'name': device_type,
                                'type': device_template.get('type', 'generic'),
                                'description': device_template.get('description', ''),
                                'sensors': [
                                    {
                                        'name': sensor.get('name', ''),
                                        'type': sensor.get('type', ''),
                                        'unit': sensor.get('unit', '')
                                    }
                                    for sensor in device_template.get('sensors', [])
                                ]
                            }
                            template['devices'].append(device)
                    
                    self.container_templates.append(template)
                    
            self.templates_count = len(self.container_templates)
            logger.info(f"Populated {self.templates_count} container templates")
            
        except Exception as e:
            logger.error(f"Error populating templates: {e}")

    def setup_templates_grid(self):
        """Setup the container templates grid"""
        try:
            # Add search field for templates
            with ui.row().classes('w-full justify-end mb-4'):
                self.template_search = ui.input(placeholder='Search templates...').classes('w-64')
                self.template_search.on('input', self.filter_templates)
                
            self.templates_grid = ui.grid(columns=3).classes('gap-4 p-4')
            
            if not self.container_templates:
                with self.templates_grid:
                    ui.label('No container templates available').classes('text-gray-500')
                return
            
            for template in self.container_templates:
                with self.templates_grid:
                    with ui.card().tight().classes('w-full') as card:
                        template['_card'] = card  # Store reference to card for filtering
                        
                        with ui.card_section().classes('min-h-[220px]'):
                            # Container header
                            with ui.row().classes('pb-2 w-full justify-between items-center border-b border-gray-200'):
                                ui.label(template['name']).classes('text-xl font-semibold')
                                with ui.badge(template['type']).classes('bg-blue-500 text-white'):
                                    pass
                            
                            # Container information
                            with ui.column().classes('py-4 gap-2'):
                                ui.label(template['description']).classes('text-sm text-gray-700')
                                with ui.row().classes('gap-1'):
                                    ui.label('Devices:').classes('text-sm font-medium')
                                    ui.label(str(len(template['devices']))).classes('text-sm')
                                with ui.row().classes('gap-1'):
                                    ui.label('Sensors:').classes('text-sm font-medium')
                                    sensors_count = sum(len(device.get('sensors', [])) for device in template['devices'])
                                    ui.label(str(sensors_count)).classes('text-sm')
                            
                            # List devices
                            if template['devices']:
                                ui.label("Devices:").classes('font-medium mt-2')
                                with ui.column().classes('ml-2'):
                                    for device in template['devices']:
                                        with ui.expansion(device['name']).classes('w-full'):
                                            with ui.column().classes('pl-4'):
                                                ui.label(device['description']).classes('text-sm text-gray-700')
                                                if device.get('sensors'):
                                                    ui.label("Sensors:").classes('text-sm font-medium mt-1')
                                                    for sensor in device['sensors']:
                                                        ui.label(f"{sensor['name']} ({sensor.get('unit', '')})").classes('text-xs ml-2')
                        
                        # Control section
                        with ui.card_section().classes('bg-gray-100'):
                            with ui.row().classes('justify-center'):
                                ui.button('Create Instance', on_click=lambda t=template: self.create_from_template(t)).classes('bg-blue-500 text-white')
                                
        except Exception as e:
            logger.error(f"Error setting up templates grid: {e}")

    def filter_templates(self, e=None):
        """Filter the template cards based on search text"""
        try:
            search_text = self.template_search.value.lower() if self.template_search.value else ""
            
            for template in self.container_templates:
                if '_card' not in template or not template['_card'].client:
                    continue
                    
                # Check if any of these fields match the search text
                name_match = search_text in template['name'].lower()
                description_match = search_text in template['description'].lower()
                room_match = search_text in template['room_type'].lower()
                
                # Check if any device names match
                device_match = any(search_text in device['name'].lower() for device in template['devices'])
                
                # Check if any sensor names match
                sensor_match = any(
                    any(search_text in sensor['name'].lower() for sensor in device.get('sensors', []))
                    for device in template['devices']
                )
                
                # Show card if any match
                if name_match or description_match or room_match or device_match or sensor_match:
                    template['_card'].classes('hidden', remove=True)
                else:
                    template['_card'].classes('hidden', add=True)
                
        except Exception as e:
            logger.error(f"Error filtering templates: {e}")

    def create_from_template(self, template):
        """Create a container instance from a template"""
        try:
            ui.notify(f"Creating container from template: {template['name']}")
            # Implementation to create a new container based on the template
            # This would need to be completed based on how containers are created in your app
            
            # Open a dialog to confirm and customize the container
            with ui.dialog(value=True) as dialog, ui.card().classes('w-96'):
                ui.label(f"Create container from {template['name']}").classes('text-lg font-bold')
                name_input = ui.input('Container Name', value=f"{template['name']} Instance").classes('w-full')
                description_input = ui.textarea('Description', value=template['description']).classes('w-full')
                
                with ui.row().classes('justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=dialog.close).classes('bg-gray-400 text-white')
                    ui.button('Create', on_click=lambda: self.confirm_create_from_template(
                        dialog, template, name_input.value, description_input.value
                    )).classes('bg-blue-500 text-white')
                    
        except Exception as e:
            logger.error(f"Error creating from template: {e}")
            ui.notify(f"Error creating container: {str(e)}", type='negative')

    def confirm_create_from_template(self, dialog, template, name, description):
        """Confirm creation of container from template"""
        try:
            logger.info(f"Creating container from template: {template['name']}")
            
            # Create a new container
            container = Container(
                name=name,
                description=description,
                container_type=template['type'],
                location=template['room_type'].replace('_', ' ').title()
            )
            
            # Save the container to get an ID
            with SessionLocal() as session:
                session.add(container)
                session.commit()
                session.refresh(container)
                
                # Create and add devices from the template
                for device_template in template['devices']:
                    device_type = device_template['name']
                    
                    # Create the device
                    device = Device(
                        name=f"{device_type} in {container.name}",
                        device_type=device_type,
                        description=device_template['description'],
                        container_id=container.id
                    )
                    
                    session.add(device)
                    session.commit()
                    session.refresh(device)
                    
                    # Create sensors for the device
                    for sensor_template in device_template.get('sensors', []):
                        sensor = Sensor(
                            name=sensor_template['name'],
                            sensor_type=sensor_template['type'],
                            unit=sensor_template.get('unit', ''),
                            device_id=device.id,
                            container_id=container.id
                        )
                        session.add(sensor)
                
                session.commit()
                
            ui.notify(f"Container '{name}' created successfully", type='positive')
            dialog.close()
            
            # Refresh containers after creation
            self.update_stats()
            self.setup_cards_grid()
            
        except Exception as e:
            logger.error(f"Error confirming container creation: {e}")
            ui.notify(f"Error creating container: {str(e)}", type='negative')

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
            logger.error(f"Error updating stats: {e}")

    def setup_cards_grid(self, active_only=None):
        """Setup the container cards grid
        
        Args:
            active_only: If True, show only active containers. If False, show only inactive containers.
                         If None, show all containers.
        """
        try:
            self.cards_grid = ui.grid(columns=3).classes('gap-4 p-4')
            self.cards = []  # Reset cards list if called multiple times
            
            # Filter containers based on active status if requested
            filtered_containers = []
            if active_only is not None:
                filtered_containers = [c for c in self.containers if c.is_active == active_only]
            else:
                filtered_containers = self.containers
            
            if not filtered_containers:
                with self.cards_grid:
                    status_msg = 'No active containers available' if active_only else 'No inactive containers available'
                    if active_only is None:
                        status_msg = 'No containers available'
                    ui.label(status_msg).classes('text-gray-500')
                return
            
            for container in filtered_containers:
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
            logger.error(f"Error setting up cards grid: {e}")

    def setup_note_label(self):
        '''Sets up the note label, which is shown when no containers are available for instance'''
        with self.cards_grid:
            self.note_label = ui.label().classes(
                'absolute left-1/2 top-48 self-center -translate-x-1/2')
            self.note_label.set_visibility(False)

    def setup_live_view_dialog(self):
        '''Sets up the live view dialog. There is only one instance of the dialog, which is reused for every container.'''
        self.live_view_dialog = LiveViewDialog(self.cards_grid)
        
        # Assign the live view dialog to all containers
        for container in self.containers:
            container.live_view_dialog = self.live_view_dialog

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
            logger.error(f"Error handling filter: {e}")

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

    def create_content(self):
        """Create the page content"""
        self.create_page()
        # Set up a periodic refresh to keep container status up-to-date
        ui.timer(5, self.refresh, active=True)
        return self
    
    def refresh(self):
        """Refresh the container data to reflect the latest state from the database"""
        self.update_stats()
        
        # Query for updated containers
        fresh_containers = Container.get_all()
        if not fresh_containers or not self.containers:
            return
            
        # Update container states if they've changed
        for i, container in enumerate(self.containers):
            # Find matching container in fresh data
            fresh_container = next((c for c in fresh_containers if c.id == container.id), None)
            if fresh_container and container.is_active != fresh_container.is_active:
                # Container status has changed, update our list
                self.containers[i] = fresh_container
                
                # If the container is displayed, update its card
                for card in self.cards:
                    if card.container.id == container.id:
                        card.container = fresh_container
                        card.update_ui()
