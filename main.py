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
from src.utils.event_system import EventSystem
from src.utils.socketio_patch import apply_socketio_patches
# Import the API router (no longer directly used, but kept for reference)
from src.api.api import api_router
from fastapi.responses import JSONResponse
# Import the state manager
from src.utils.state_manager import StateManager

# Configure logging
os.makedirs('logs', exist_ok=True)
logger.add("logs/app.log", rotation="500 MB", level="INFO")

# Create a global event system instance
event_system = EventSystem.get_instance()
logger.info("Global EventSystem instance created")

# Create a global state manager instance
state_manager = StateManager()
logger.info("Global StateManager instance created")

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
    
    # Set up API routes directly using ui.page
    @ui.page('/api/devices')
    async def get_devices():
        """Get all devices or filter by type/room"""
        from fastapi.responses import JSONResponse
        from src.database import SessionLocal
        from src.models.device import Device

        try:
            with SessionLocal() as session:
                devices = session.query(Device).all()
                device_list = [{"id": d.id, "name": d.name, "type": d.type, "room_id": d.room_id} for d in devices]
                return JSONResponse(content={"devices": device_list})
        except Exception as e:
            logger.error(f"Error fetching devices: {str(e)}")
            return JSONResponse(content={"error": str(e)}, status_code=500)
    
    @ui.page('/api/devices/{device_id}')
    async def get_device(request):
        """Get detailed information about a specific device"""
        from fastapi.responses import JSONResponse
        from src.database import SessionLocal
        from src.models.device import Device
        from src.models.sensor import Sensor

        try:
            device_id = int(request.path_params.get('device_id'))
            with SessionLocal() as session:
                device = session.query(Device).filter(Device.id == device_id).first()
                if not device:
                    return JSONResponse(content={"error": "Device not found"}, status_code=404)
                
                # Get all sensors for this device
                sensors = session.query(Sensor).filter(Sensor.device_id == device_id).all()
                sensor_list = [
                    {
                        "id": s.id, 
                        "name": s.name, 
                        "type": s.type, 
                        "current_value": s.current_value, 
                        "unit": s.unit
                    } 
                    for s in sensors
                ]
                
                # Create detailed device info
                device_info = {
                    "id": device.id,
                    "name": device.name,
                    "type": device.type,
                    "room_id": device.room_id,
                    "description": device.description,
                    "is_active": device.is_active,
                    "sensors": sensor_list
                }
                
                return JSONResponse(content=device_info)
        except Exception as e:
            logger.error(f"Error fetching device details: {str(e)}")
            return JSONResponse(content={"error": str(e)}, status_code=500)
    
    @ui.page('/api/rooms')
    async def get_rooms():
        """Get all rooms"""
        from fastapi.responses import JSONResponse
        from src.database import SessionLocal
        from src.models.room import Room
        from src.models.device import Device

        try:
            with SessionLocal() as session:
                rooms = session.query(Room).all()
                result = []
                
                for room in rooms:
                    # Get devices in this room
                    devices = session.query(Device).filter(Device.room_id == room.id).all()
                    device_list = [{"id": d.id, "name": d.name, "type": d.type} for d in devices]
                    
                    room_data = {
                        "id": room.id,
                        "name": room.name,
                        "room_type": room.room_type,
                        "is_indoor": room.is_indoor,
                        "devices": device_list
                    }
                    result.append(room_data)
                
                return JSONResponse(content={"rooms": result})
        except Exception as e:
            logger.error(f"Error fetching rooms: {str(e)}")
            return JSONResponse(content={"error": str(e)}, status_code=500)
    
    # More API endpoints can be added in a similar way, as needed
    logger.info("API endpoints set up at /api/*")
    
    # Attempt to apply Socket.IO patches but continue even if they fail
    try:
        patch_result = apply_socketio_patches()
        if not patch_result:
            logger.warning("Socket.IO patches not fully applied - some features may have limited functionality")
        else:
            logger.info("Socket.IO patches applied successfully")
    except Exception as e:
        logger.error(f"Error applying Socket.IO patches: {e}")
        logger.warning("Continuing without Socket.IO patches - some features may have limited functionality")

    # Database setup
    ensure_database()
    initialize_all_data()
    
    # Initialize services
    iot_hub_helper = IoTHubHelper()

    # Create routes
    @ui.page('/')
    def home():
        """Create the main application page with navigation tabs"""
        nav = Navigation()
        with ui.header().style('background-color: #3874c8').classes('z-50'):
            nav.setup_navigation()
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            create_intro_content()

    @ui.page('/smart_home')
    def smart_home():
        """Smart Home visualization page"""
        try:
            nav = Navigation()
            with ui.header().style('background-color: #3874c8').classes('z-50'):
                nav.setup_navigation()
            with ui.column().classes('w-full min-h-screen bg-gray-50'):
                smart_home_page = SmartHomePage(event_system, state_manager)
                smart_home_page.build()
        except Exception as e:
            logger.error(f"Error loading smart home page: {str(e)}")
            with ui.column().classes('w-full p-4'):
                ui.label('Error loading smart home page:').classes('text-red-500 font-bold')
                ui.label(str(e)).classes('text-red-500')

    @ui.page('/containers')
    def containers():
        """Containers management page"""
        nav = Navigation()
        with ui.header().style('background-color: #3874c8').classes('z-50'):
            nav.setup_navigation()
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            containers_page = ContainersPage(iot_hub_helper=iot_hub_helper, event_system=event_system, state_manager=state_manager)
            containers_page.create_content()

    @ui.page('/devices')
    def devices():
        """Devices management page"""
        nav = Navigation()
        with ui.header().style('background-color: #3874c8').classes('z-50'):
            nav.setup_navigation()
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            devices_page = DevicesPage(iot_hub_helper=iot_hub_helper, event_system=event_system, state_manager=state_manager)
            devices_page.create_content()

    @ui.page('/sensors')
    def sensors():
        """Sensors management page"""
        nav = Navigation()
        with ui.header().style('background-color: #3874c8').classes('z-50'):
            nav.setup_navigation()
        with ui.column().classes('w-full min-h-screen bg-gray-50'):
            sensors_page = SensorsPage(iot_hub_helper=iot_hub_helper, event_system=event_system, state_manager=state_manager)
            sensors_page.create_content()

    @ui.page('/debug_sensors')
    def debug_sensors():
        with SessionLocal() as session:
            sensors = session.query(Sensor).all()
            return [f"{s.name}: {s.current_value}" for s in sensors]

    # Add a page to display API documentation
    @ui.page('/api-docs')
    def api_docs():
        """API Documentation page"""
        nav = Navigation()
        with ui.header().style('background-color: #3874c8').classes('z-50'):
            nav.setup_navigation()
        with ui.column().classes('w-full min-h-screen bg-gray-50 p-4'):
            with ui.card().classes('w-full p-4'):
                ui.label('Smart Home API Documentation').classes('text-h5 mb-4')
                ui.label('This page provides documentation for the Smart Home RESTful API.').classes('mb-4')
                
                with ui.expansion('API Overview', icon='api').classes('w-full'):
                    ui.label('The Smart Home API provides endpoints to control smart home devices:').classes('mb-2')
                    with ui.list().classes('ml-4'):
                        ui.label('GET /api/devices - List all devices')
                        ui.label('GET /api/devices/{device_id} - Get details for a specific device')
                        ui.label('GET /api/rooms - List all rooms with their devices')
                
                with ui.expansion('Example Usage (cURL)', icon='code').classes('w-full mt-4'):
                    with ui.code('bash').classes('w-full'):
                        ui.markdown('''
# Get all devices
curl -X GET "http://localhost:8080/api/devices"

# Get a specific device with its sensors
curl -X GET "http://localhost:8080/api/devices/20"

# Get all rooms with their devices
curl -X GET "http://localhost:8080/api/rooms"
                        ''')

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
