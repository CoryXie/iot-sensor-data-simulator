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
from src.database import Base, engine, init_db, ensure_database, SessionLocal
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
    with ui.column().classes("w-full h-full p-4 gap-4"):
        # Welcome card
        with ui.card().classes("w-full p-6 bg-white shadow-lg rounded-xl"):
            with ui.column().classes("gap-4"):
                ui.label("Welcome to Smart Home IoT Platform").classes("text-2xl font-bold text-blue-600")
                ui.label("""
                    This platform provides comprehensive IoT device management and monitoring capabilities 
                    for your smart home. Navigate through different sections using the tabs above.
                """).classes("text-gray-600")
        
        # Quick links grid
        with ui.grid(columns=3).classes("w-full gap-4"):
            # Smart Home Card
            with ui.card().classes("p-4 bg-white shadow hover:shadow-lg transition-shadow"):
                ui.icon("home").classes("text-4xl text-blue-500")
                ui.label("Smart Home").classes("text-lg font-bold mt-2")
                ui.label("Monitor and control your smart home devices in real-time").classes("text-sm text-gray-600")
                ui.button("Open", icon="arrow_forward", on_click=lambda: ui.open('/smart_home')).classes("mt-4")
            
            # Devices Card
            with ui.card().classes("p-4 bg-white shadow hover:shadow-lg transition-shadow"):
                ui.icon("devices").classes("text-4xl text-green-500")
                ui.label("Devices").classes("text-lg font-bold mt-2")
                ui.label("Manage all your IoT devices and their configurations").classes("text-sm text-gray-600")
                ui.button("Open", icon="arrow_forward", on_click=lambda: ui.open('/devices')).classes("mt-4")
            
            # Sensors Card
            with ui.card().classes("p-4 bg-white shadow hover:shadow-lg transition-shadow"):
                ui.icon("sensors").classes("text-4xl text-purple-500")
                ui.label("Sensors").classes("text-lg font-bold mt-2")
                ui.label("View and analyze data from all connected sensors").classes("text-sm text-gray-600")
                ui.button("Open", icon="arrow_forward", on_click=lambda: ui.open('/sensors')).classes("mt-4")
        
        # Features section
        with ui.card().classes("w-full p-6 bg-white shadow-lg rounded-xl mt-4"):
            ui.label("Key Features").classes("text-xl font-bold mb-4")
            with ui.grid(columns=2).classes("gap-4"):
                features = [
                    ("Real-time Monitoring", "View live sensor data and device states", "monitoring"),
                    ("Smart Scenarios", "Create and manage automated scenarios", "auto_mode"),
                    ("Device Management", "Add, configure and control IoT devices", "device_hub"),
                    ("Data Analytics", "Analyze sensor data and usage patterns", "analytics")
                ]
                for title, desc, icon in features:
                    with ui.row().classes("items-center gap-4 p-4 rounded-lg bg-gray-50"):
                        ui.icon(icon).classes("text-2xl text-blue-500")
                        with ui.column():
                            ui.label(title).classes("font-bold")
                            ui.label(desc).classes("text-sm text-gray-600")

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
        """Create the main application page with navigation tabs"""
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            # Create navigation at the top
            nav = Navigation()
            nav.setup_navigation()
            
            # Create the introduction content
            create_intro_content()

    @ui.page('/smart_home')
    def smart_home():
        """Smart Home visualization page"""
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            nav = Navigation()
            nav.setup_navigation()
            smart_home_page = SmartHomePage()
            smart_home_page.create_content()

    @ui.page('/containers')
    def containers():
        """Containers management page"""
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            nav = Navigation()
            nav.setup_navigation()
            containers_page = ContainersPage(iot_hub_helper=iot_hub_helper)
            containers_page.create_content()

    @ui.page('/devices')
    def devices():
        """Devices management page"""
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            nav = Navigation()
            nav.setup_navigation()
            devices_page = DevicesPage(iot_hub_helper=iot_hub_helper)
            devices_page.create_content()

    @ui.page('/sensors')
    def sensors():
        """Sensors management page"""
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            nav = Navigation()
            nav.setup_navigation()
            sensors_page = SensorsPage(iot_hub_helper=iot_hub_helper)
            sensors_page.create_content()

    @ui.page('/debug_sensors')
    def debug_sensors():
        with SessionLocal() as session:
            sensors = session.query(Sensor).all()
            return [f"{s.name}: {s.current_value}" for s in sensors]

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
