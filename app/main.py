from nicegui import ui
from pages.containers_page import ContainersPage
from pages.devices_page import DevicesPage
from pages.sensors_page import SensorsPage
from pages.smart_home_page import SmartHomePage
from database import init_db, db_session
from utils.iot_hub_helper import IoTHubHelper
from loguru import logger
import os

# Configure logging
os.makedirs('logs', exist_ok=True)
logger.add("logs/app.log", rotation="500 MB", level="INFO")

# Global variables
pages = None
iot_hub_helper = None

def init():
    """Initialize the application"""
    global pages, iot_hub_helper
    
    logger.info("Initializing application")
    try:
        # Initialize database
        init_db()
        
        # Initialize IoT Hub helper
        iot_hub_helper = IoTHubHelper()
        logger.info("IoT Hub helper initialized")
        
        # Initialize pages dictionary
        pages = {}
        
        # Initialize pages
        pages['containers'] = ContainersPage(iot_hub_helper)
        pages['devices'] = DevicesPage(iot_hub_helper)
        pages['sensors'] = SensorsPage()
        pages['smart_home'] = SmartHomePage()
        
        logger.info("Application initialized successfully")
    except Exception as e:
        logger.exception(f"Error initializing application: {str(e)}")
        raise

@ui.page('/')
def home():
    """Home page"""
    if pages is None:
        init()
        
    with ui.tabs().classes('w-full') as tabs:
        ui.tab('Smart Home', icon='home')
        ui.tab('Containers', icon='inventory_2')
        ui.tab('Devices', icon='devices')
        ui.tab('Sensors', icon='sensors')
    
    with ui.tab_panels(tabs, value='Smart Home').classes('w-full'):
        with ui.tab_panel('Smart Home'):
            pages['smart_home'].create_page()
        with ui.tab_panel('Containers'):
            pages['containers'].create_page()
        with ui.tab_panel('Devices'):
            pages['devices'].create_page()
        with ui.tab_panel('Sensors'):
            pages['sensors'].create_page()

if __name__ in {"__main__", "__mp_main__"}:
    init()
    ui.run(title='IoT Sensor Data Simulator', favicon='🏠')
