from nicegui import ui
from pages.sensors_page import SensorsPage
from pages.containers_page import ContainersPage
from pages.devices_page import DevicesPage
from pages.smart_home_page import SmartHomePage
from utils.mqtt_helper import MQTTHelper
from utils.iot_hub_helper import IoTHubHelper
from utils.init_db import init_database
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize database
engine, session = init_database()

# Initialize helpers
mqtt_helper = None  # Will be initialized per container
iot_hub_helper = IoTHubHelper()

# Initialize pages
containers_page = ContainersPage(iot_hub_helper=iot_hub_helper)
devices_page = DevicesPage(iot_hub_helper=iot_hub_helper)
sensors_page = SensorsPage()
smart_home_page = SmartHomePage()

@ui.page('/')
def main_page():
    """Main page of the application"""
    # Add header
    with ui.header().classes('bg-blue-800 text-white'):
        with ui.row().classes('w-full items-center justify-between p-4'):
            ui.label('IOT TELEMETRY SIMULATOR').classes('text-xl')
            with ui.row().classes('items-center gap-4'):
                ui.label('IoT Hub: Not Configured')
                ui.switch('Demo Mode')
    
    with ui.tabs().classes('w-full') as tabs:
        containers_tab = ui.tab('Containers')
        devices_tab = ui.tab('Devices')
        sensors_tab = ui.tab('Sensors')
        smart_home_tab = ui.tab('Smart Home')

    with ui.tab_panels(tabs, value=containers_tab).classes('w-full'):
        with ui.tab_panel(containers_tab):
            containers_page.create_page()
        with ui.tab_panel(devices_tab):
            devices_page.create_page()
        with ui.tab_panel(sensors_tab):
            sensors_page.create_page()
        with ui.tab_panel(smart_home_tab):
            smart_home_page.create_page()

    # Add page styling
    ui.add_head_html('''
        <style>
        .q-tab-panels {
            background-color: #f5f5f5;
        }
        .q-tab--active {
            color: #1976d2;
            font-weight: bold;
        }
        .q-card {
            margin-bottom: 1rem;
        }
        </style>
    ''')

ui.run(title='IoT Sensor Data Simulator', port=8080)
