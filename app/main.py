from nicegui import ui
from pages.containers_page import ContainersPage
from pages.devices_page import DevicesPage
from pages.sensors_page import SensorsPage
from pages.smart_home_page import SmartHomePage
from utils.iot_hub_helper import IoTHubHelper
from database import init_db
import socket

# Global page instances
pages = {}

def find_free_port(start_port=8080, max_tries=10):
    """Find a free port starting from start_port"""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue
    return start_port  # Fallback to original port if no free port found

def main():
    # Initialize database
    init_db()
    
    # Initialize IoT Hub Helper
    iot_hub_helper = IoTHubHelper()
    
    # Create pages
    global pages
    pages['containers'] = ContainersPage(iot_hub_helper)
    pages['devices'] = DevicesPage(iot_hub_helper)
    pages['sensors'] = SensorsPage()
    pages['smart_home'] = SmartHomePage()
    
    # Setup navigation
    @ui.page('/')
    def containers():
        _create_header()
        pages['containers'].create_page()
        
    @ui.page('/devices')
    def devices():
        _create_header()
        pages['devices'].create_page()
        
    @ui.page('/sensors')
    def sensors():
        _create_header()
        pages['sensors'].create_page()
        
    @ui.page('/smart-home')
    def smart_home():
        _create_header()
        pages['smart_home'].create_page()
    
    # Find a free port
    port = find_free_port()
    
    # Run the app
    ui.run(port=port, reload=False)

def _create_header():
    """Create the application header with navigation"""
    with ui.header().classes('bg-blue-500 text-white'):
        ui.label('IoT Sensor Data Simulator').classes('text-2xl p-4')
        
    with ui.row().classes('w-full bg-blue-100 p-2'):
        ui.link('Containers', '/').classes('p-2 hover:bg-blue-200 rounded')
        ui.link('Devices', '/devices').classes('p-2 hover:bg-blue-200 rounded')
        ui.link('Sensors', '/sensors').classes('p-2 hover:bg-blue-200 rounded')
        ui.link('Smart Home', '/smart-home').classes('p-2 hover:bg-blue-200 rounded')

if __name__ == '__main__':
    main()
