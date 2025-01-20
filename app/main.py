from nicegui import ui
from pages.containers_page import ContainersPage
from pages.devices_page import DevicesPage
from pages.sensors_page import SensorsPage
from pages.smart_home_page import SmartHomePage
from database import init_db, db_session
from utils.iot_hub_helper import IoTHubHelper
from loguru import logger
import os
from models.container import Container
from components.navigation import Navigation

# Configure logging
os.makedirs('logs', exist_ok=True)
logger.add("logs/app.log", rotation="500 MB", level="INFO")

def init():
    """Initialize the application"""
    try:
        logger.info("Initializing application")
        
        # Initialize database and stop all scenarios
        init_db()
        Container.stop_all()
        
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
    init()
    ui.run(title='IoT Sensor Data Simulator', favicon='🏠')
