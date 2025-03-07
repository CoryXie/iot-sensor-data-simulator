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

    def setup_navigation(self):
        '''Sets up the navigation bar with all pages'''
        try:
            # Only read the demo mode value, don't set it
            is_demo_mode = Option.get_value("demo_mode") == "true"
            
            with ui.row().classes('mx-auto w-screen max-w-screen-2xl justify-between lg:px-8 lg:items-center'):
                # Title and Home Link
                ui.link("SmartHome IoT Platform", "/").classes(
                    'text-xl font-semibold text-white !no-underline')
                
                # Navigation links
                with ui.row().classes('mx-auto gap-6 order-2 sm:order-[0] lg:mx-0 lg:gap-8'):
                    ui.link('Smart Home', '/smart_home').classes('text-white !no-underline hover:text-blue-200')
                    ui.link('Containers', '/containers').classes('text-white !no-underline hover:text-blue-200')
                    ui.link('Devices', '/devices').classes('text-white !no-underline hover:text-blue-200')
                    ui.link('Sensors', '/sensors').classes('text-white !no-underline hover:text-blue-200')
                    ui.link('API Docs', '/api-docs').classes('text-white !no-underline hover:text-blue-200 flex items-center')
                
                # Settings area
                with ui.row().classes('flex items-center gap-4'):
                    # Display IoT Hub host name
                    host_name = self.host_name if self.host_name else 'Not Configured'
                    self.host_name_label = ui.label(f'IoT Hub: {host_name}').classes('text-white text-sm')
                    
                    # Demo mode switch
                    with ui.row().classes('items-center gap-2'):
                        self.demo_switch = ui.switch('Demo', on_change=self.on_demo_toggle).classes('text-white')
                        with self.demo_switch:
                            ui.tooltip('When enabled, no messages will be sent to IoT Hub or MQTT broker.')
                        self.demo_switch.value = is_demo_mode
                            
        except Exception as e:
            logger.error(f"Error setting up navigation: {e}")
            raise

    def on_demo_toggle(self, event: dict):
        """Toggle demo mode"""
        try:
            with SessionLocal() as session:
                new_value = event.value
                Option.set_value('demo_mode', str(new_value).lower())
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
