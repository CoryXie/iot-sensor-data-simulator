from nicegui import ui
from models.option import Option
from utils.iot_hub_helper import IoTHubHelper
from loguru import logger


class Navigation():
    '''Navigation component for displaying the navigation bar'''

    def __init__(self):
        '''Initializes the navigation bar'''
        self.host_name = IoTHubHelper.get_host_name()
        self.tabs = None
        logger.debug("Initialized Navigation component")
        self.setup()

    def setup(self):
        '''Sets up the UI elements of the navigation bar'''
        with ui.header(elevated=True).style('background-color: #3874c8').classes(' z-50'):
            with ui.row().classes('mx-auto w-screen max-w-screen-2xl justify-between lg:px-8 lg:items-center'):
                # Title
                ui.label("SmartHome Sensors Simulator").classes(
                    'text-md font-semibold uppercase')
                # Navigation list
                with ui.row().classes('mx-auto gap-6 order-2 sm:order-[0] lg:mx-0 lg:gap-12'):
                    ui.link('Container', '/').classes('text-white !no-underline')
                    ui.link('Devices', '/geraete').classes('text-white !no-underline')
                    ui.link('Sensors', '/sensoren').classes('text-white !no-underline')
                # Settings
                with ui.row().classes('flex-col gap-0 items-center lg:flex-row lg:gap-4 lg:divide-x lg:divide-white/50'):
                    # Display IoT Hub host name
                    host_name = self.host_name if self.host_name else 'Not Configured'
                    self.host_name_label = ui.label(f'IoT Hub: {host_name}').classes('text-white')
                    
                    # Demo mode switch with error handling
                    try:
                        demo_switch = ui.switch('Demo Mode', on_change=self.demo_switch_handler).classes('text-white')
                        with demo_switch:
                            ui.tooltip('When enabled, no messages will be sent to IoT Hub or MQTT broker.')
                        demo_switch.value = Option.get_boolean('demo_mode')
                        ui.query('.q-toggle__inner--falsy').classes('!text-white/50')
                    except Exception as e:
                        logger.error(f"Error setting up demo switch: {str(e)}")
                        demo_switch = ui.switch('Demo Mode', value=False).classes('text-white disabled')

    def demo_switch_handler(self, switch):
        '''Handles the switch change event of the demo mode switch'''
        try:
            Option.set_value('demo_mode', str(switch.value).lower())
            if switch.value:
                ui.query('.q-toggle__inner--truthy').classes('!text-white')
                ui.query('.q-toggle__inner--falsy').classes(remove='!text-white/50')
            else:
                ui.query('.q-toggle__inner--falsy').classes('!text-white/50')
                ui.query('.q-toggle__inner--truthy').classes(remove='!text-white')
        except Exception as e:
            logger.error(f"Error handling demo switch change: {str(e)}")

    def create_navigation(self):
        """Create the navigation tabs"""
        with ui.tabs().classes('w-full') as self.tabs:
            ui.tab('Smart Home', icon='home')
            ui.tab('Containers', icon='inventory_2')
            ui.tab('Devices', icon='devices')
            ui.tab('Sensors', icon='sensors')
