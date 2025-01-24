from nicegui import ui
from src.pages.containers_page import ContainersPage
from src.pages.devices_page import DevicesPage
from src.pages.sensors_page import SensorsPage
from src.pages.smart_home_page import SmartHomePage
# Import models at the top, before init() is called
from src.models.option import Option
from src.models.container import Container
from src.models.device import Device
from src.models.sensor import Sensor
from src.utils.db_utils import init_db, shutdown_db # Correct import path
from src.utils.iot_hub_helper import IoTHubHelper
from loguru import logger
import os
from src.models.container import Container
from src.components.navigation import Navigation








# Configure logging
os.makedirs('logs', exist_ok=True)
logger.add("logs/app.log", rotation="500 MB", level="INFO")

def init():
    """Initialize the application"""
    try:
        logger.info("Initializing application")
        
        # Initialize database first
        init_db()
        
        # After database is initialized, stop all containers
        try:
            Container.stop_all()
        except Exception as e:
            logger.warning(f"Error stopping containers: {str(e)}")
        
        # Initialize IoT Hub helper
        iot_hub = IoTHubHelper()
        logger.info("IoT Hub helper initialized")
        
        # Create pages
        smart_home_page = SmartHomePage()
        containers_page = ContainersPage(iot_hub)
        devices_page = DevicesPage(iot_hub)
        sensors_page = SensorsPage()
        
        # Create navigation
        navigation = Navigation()
        
        # Create routes
        @ui.page('/')
        def home():
            navigation.create_navigation()
            with ui.tab_panels(navigation.tabs, value='Smart Home').classes('w-full'):
                with ui.tab_panel('Smart Home'):
                    smart_home_page.create_page()
                with ui.tab_panel('Containers'):
                    containers_page.create_page()
                with ui.tab_panel('Devices'):
                    devices_page.create_page()
                with ui.tab_panel('Sensors'):
                    sensors_page.create_page()
            
        logger.info("Application initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing application: {str(e)}")
        raise

if __name__ in {"__main__", "__mp_main__"}:
    try:
        init()
        ui.run(title='IoT Sensor Data Simulator', favicon='🏠')
    finally:
        shutdown_db()
