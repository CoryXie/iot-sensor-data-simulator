from nicegui import ui
from src.models.option import Option
from src.utils.iot_hub_helper import IoTHubHelper
from loguru import logger
from src.database import SessionLocal


class Navigation():
    '''Navigation component for displaying the navigation bar'''

    def __init__(self, on_demo_toggle_callback=None):
        '''Initializes the navigation bar'''
        self.host_name = IoTHubHelper.get_host_name()
        self.tabs = None
        self.header = None
        self.demo_switch = None
        self.on_demo_toggle_callback = on_demo_toggle_callback
        logger.debug("Initialized Navigation component")
        self.setup()

    def setup(self):
        '''Sets up the UI elements of the navigation bar'''
        try:
            # Use get_value and convert to boolean
            is_demo_mode = bool(Option.get_value("demo_mode"))
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
                            self.demo_switch = ui.switch('Demo Mode', on_change=self.on_demo_toggle).classes('text-white')
                            with self.demo_switch:
                                ui.tooltip('When enabled, no messages will be sent to IoT Hub or MQTT broker.')
                            self.demo_switch.value = is_demo_mode
                            ui.query('.q-toggle__inner--falsy').classes('!text-white/50')
                        except Exception as e:
                            logger.error(f"Error setting up demo switch: {str(e)}")
                            self.demo_switch = ui.switch('Demo Mode', value=False).classes('text-white disabled')

        except Exception as e:
            logger.error(f"Error setting up navigation: {e}")

    def on_demo_toggle(self, event: dict):
        """Toggle demo mode"""
        try:
            with SessionLocal() as session:  # Use proper session
                option = session.query(Option).filter_by(name='demo_mode').first()
                new_value = not (option.value.lower() == 'true') if option else True
                Option.set_value('demo_mode', str(new_value))
                self.demo_mode = new_value
                ui.notify(f"Demo mode {'enabled' if new_value else 'disabled'}")
        except Exception as e:
            logger.error(f"Error toggling demo mode: {str(e)}")
            raise

    def create_navigation(self):
        """Create the main navigation tabs"""
        self.tabs = ui.tabs().classes('w-full')
        with self.tabs:
            ui.tab('Smart Home')
            ui.tab('Containers')
            ui.tab('Devices')
            ui.tab('Sensors')
