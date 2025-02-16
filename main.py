import sys
import os

# Add this at the very top of main.py
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from nicegui import ui, app
from src.pages.containers_page import ContainersPage
from src.pages.devices_page import DevicesPage
from src.pages.sensors_page import SensorsPage
from src.pages.smart_home_page import SmartHomePage
# Import models at the top, before init() is called
from src.models.option import Option
from src.models.container import Container
from src.models.device import Device
from src.models.sensor import Sensor
from src.utils.iot_hub_helper import IoTHubHelper
from loguru import logger
from src.components.navigation import Navigation
from src.database import Base, engine, init_db, ensure_database
from sqlalchemy import inspect as sa_inspect
from src.models.model_registry import register_models
import signal
import sys
from src.utils.initial_data import initialize_all_data, initialize_rooms, initialize_options
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Configure logging
os.makedirs('logs', exist_ok=True)
logger.add("logs/app.log", rotation="500 MB", level="INFO")

def create_intro_content():
    """Create modern introduction content"""
    with ui.column().classes("w-full h-full p-8 space-y-8"):
        # Hero Section
        with ui.row().classes("w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-2xl p-8 shadow-2xl"):
            with ui.column().classes("space-y-4"):
                ui.label("Smart Home Intelligence Platform").classes("text-4xl font-bold")
                ui.label("Next Generation IoT Management System").classes("text-xl")
                with ui.row().classes("space-x-4 mt-4"):
                    ui.button("Get Started", icon="rocket", color="positive").classes("px-8 py-4")
                    ui.button("Learn More", icon="info", color="white").classes("px-8 py-4 text-blue-600")
            ui.image("https://cdn-icons-png.flaticon.com/512/1067/1067555.png").classes("w-64 h-64")

        # Features Grid
        with ui.grid(columns=3).classes("w-full gap-8"):
            features = [
                ("speed", "Real-time Monitoring", "Instant sensor data visualization"),
                ("settings_input_hdmi", "Automation", "Smart scenario configurations"),
                ("security", "Security", "Enterprise-grade protection"),
                ("device_hub", "IoT Integration", "100+ supported devices"),
                ("insights", "Analytics", "Advanced data insights"),
                ("support_agent", "24/7 Support", "Always here to help")
            ]
            
            for icon, title, desc in features:
                with ui.card().classes("w-full p-6 transition-all hover:scale-105 hover:shadow-xl"):
                    with ui.column().classes("items-center text-center space-y-4"):
                        ui.icon(icon).classes("text-4xl text-blue-600")
                        ui.label(title).classes("text-xl font-semibold")
                        ui.label(desc).classes("text-gray-600")

        # Stats Section
        with ui.row().classes("w-full bg-gray-50 rounded-2xl p-8 justify-between"):
            stats = [
                ("1M+", "Devices Connected"),
                ("99.9%", "Uptime Reliability"),
                ("150+", "Supported Protocols"),
                ("24/7", "Monitoring")
            ]
            for value, label in stats:
                with ui.column().classes("items-center"):
                    ui.label(value).classes("text-3xl font-bold text-blue-600")
                    ui.label(label).classes("text-gray-500")

def init():
    """Initialize the application"""
    logger.info("Initializing application")
    
    # Database setup
    ensure_database()
    initialize_all_data()
    
    # Initialize services
    iot_hub_helper = IoTHubHelper()

    # Create routes
    @ui.page('/')
    def home():
        """Main application page with tabs"""
        # Create page instances
        smart_home_page = SmartHomePage()
        containers_page = ContainersPage(iot_hub_helper=iot_hub_helper)
        devices_page = DevicesPage(iot_hub_helper=iot_hub_helper)
        sensors_page = SensorsPage(iot_hub_helper=iot_hub_helper)

        # Main layout
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            # Navigation tabs
            with ui.tabs().classes('w-full bg-white rounded-lg shadow-sm') as tabs:
                intro_tab = ui.tab('Introduction').classes('px-6 py-3')
                ui.tab('Smart Home').classes('px-6 py-3')
                ui.tab('Containers').classes('px-6 py-3')
                ui.tab('Devices').classes('px-6 py-3') 
                ui.tab('Sensors').classes('px-6 py-3')
            
            # Tab content panels
            with ui.tab_panels(tabs, value=intro_tab).classes('w-full h-full'):
                # Introduction page
                with ui.tab_panel(intro_tab).classes('p-4 bg-white rounded-lg shadow-sm'):
                    create_intro_content()
                
                # Smart Home Dashboard
                with ui.tab_panel('Smart Home').classes('p-4 bg-white rounded-lg shadow-sm'):
                    smart_home_page.create_content()
                
                # Container Management
                with ui.tab_panel('Containers').classes('p-4 bg-white rounded-lg shadow-sm'):
                    containers_page.create_content()
                
                # Device Configuration
                with ui.tab_panel('Devices').classes('p-4 bg-white rounded-lg shadow-sm'):
                    devices_page.create_content()
                
                # Sensor Monitoring
                with ui.tab_panel('Sensors').classes('p-4 bg-white rounded-lg shadow-sm'):
                    sensors_page.create_content()

        logger.info("Application initialized successfully")

def handle_shutdown(signum, frame):
    logger.warning("Received shutdown signal")
    engine.dispose()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

if __name__ in {"__main__", "__mp_main__"}:
    try:
        init()
        ui.run(title='IoT Sensor Data Simulator', favicon='🏠')
    except Exception as e:
        logger.error(f"Error starting application: {str(e)}")
        raise
    finally:
        engine.dispose()
