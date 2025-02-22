from src.models.room import Room
from src.models.device import Device
from src.models.sensor import Sensor
from src.database import SessionLocal
from loguru import logger
from src.constants.device_templates import DEVICE_TEMPLATES, SCENARIO_TEMPLATES, ROOM_TEMPLATES
from src.models.scenario import Scenario
from src.models.container import Container
from src.database.database import db_session
from src.models import Option
import uuid

def initialize_rooms():
    """Initialize rooms with proper session handling"""
    with SessionLocal() as session:
        try:
            logger.info("Initializing rooms...")
            for room_name, template in ROOM_TEMPLATES.items():
                if not session.query(Room).filter_by(name=room_name).first():
                    room = Room(
                        name=room_name,
                        room_type=template['room_type'],
                        description=template['description']
                    )
                    session.add(room)
            session.commit()
            logger.success("Rooms initialized successfully.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error initializing rooms: {e}")
            raise

# Comment out or delete the entire initialize_rooms_with_sensors function
# def initialize_rooms_with_sensors():
#     """Initialize rooms with their devices and sensors"""
#     db = SessionLocal()
#     try:
#         # Define rooms
#         rooms = [
#             Room(name='Living Room', room_type='living_room'),
#             Room(name='Kitchen', room_type='kitchen'),
#             Room(name='Bedroom', room_type='bedroom'),
#             Room(name='Bathroom', room_type='bathroom'),
#             Room(name='Office', room_type='office'),
#             Room(name='Garage', room_type='garage')
#         ]
#         db.add_all(rooms)
#         db.commit()
#         logger.info("Created rooms successfully")
#         # ... rest of the function ...
#     except Exception as e:
#         db.rollback()
#         logger.error(f"Error initializing rooms: {str(e)}")
#         raise
#     finally:
#         db.close()

def initialize_scenarios():
    """Initialize scenarios from templates"""
    with SessionLocal() as session:
        # Clear existing data
        session.query(Container).delete()
        session.query(Scenario).delete()
        
        for scenario_name, config in SCENARIO_TEMPLATES.items():
            # Create scenario
            scenario = Scenario(
                name=scenario_name,
                scenario_type=config['type'],
                description=config['description'],
                is_active=config.get('is_active', False)
            )
            
            # Create container with unique name
            container = Container(
                name=f"{scenario_name} Container - {uuid.uuid4().hex[:6]}",
                container_type='scenario',
                description=f"Container for {scenario_name} scenario",
                interval=config.get('interval', 5)
            )
            
            # Create devices for this container
            devices = []
            for device_type in config['devices']:
                device = Device(
                    name=f"{scenario_name} {device_type}",
                    type=device_type
                )
                device.is_active = True  # Set after creation
                
                # Add sensors based on device type
                if device_type in DEVICE_TEMPLATES:
                    for sensor_config in DEVICE_TEMPLATES[device_type]['sensors']:
                        sensor = Sensor(**sensor_config)
                        device.sensors.append(sensor)
                
                devices.append(device)
            
            container.devices = devices
            scenario.containers.append(container)
            
            session.add(scenario)
        
        session.commit()
    logger.success("Scenarios initialized from templates")

def initialize_options():
    """Initialize default options if not already set"""
    with db_session() as session:  # Use context manager properly
        try:
            logger.info("Initializing default options...")
            if not Option.get_value('demo_mode'):
                Option.set_value('demo_mode', 'false')
                logger.debug("Setting default option: demo_mode = false")
            if not Option.get_value('mqtt_enabled'):
                Option.set_value('mqtt_enabled', 'true')
                logger.debug("Setting default option: mqtt_enabled = true")
            if not Option.get_value('simulation_interval'):
                Option.set_value('simulation_interval', '5')
                logger.debug("Setting default option: simulation_interval = 5")
            session.commit()  # Commit inside the context manager
            logger.success("Default options initialized.")
        except Exception as e:
            session.rollback()  # Rollback inside the context manager
            logger.error(f"Option initialization failed: {e}")
            raise

def initialize_devices_and_sensors():
    with SessionLocal() as session:
        try:
            session.query(Sensor).delete()
            session.query(Device).delete()
            
            for room_name, template in ROOM_TEMPLATES.items():
                room = session.query(Room).filter_by(name=room_name).first()
                if not room:
                    continue
                
                for device_name in template['devices']:
                    device_template = DEVICE_TEMPLATES[device_name]
                    # Create device with proper room association
                    device = Device(
                        name=f"{room_name} {device_name}",
                        type=device_template['type']
                    )
                    device.room = room  # Set relationship
                    session.add(device)
                    session.flush()
                    
                    # Create sensors and link to room
                    for sensor_template in device_template['sensors']:
                        sensor = Sensor(
                            name=sensor_template['name'],
                            type=sensor_template['type'],
                            unit=sensor_template.get('unit'),
                            min_value=sensor_template.get('min_value', 0),
                            max_value=sensor_template.get('max_value', 100),
                            variation_range=sensor_template.get('variation_range', 1.0),
                            change_rate=sensor_template.get('change_rate', 0.1),
                            interval=sensor_template.get('interval', 5),
                            room=room  # Now matches constructor
                        )
                        sensor.device = device
                        session.add(sensor)
            
            session.commit()
            logger.success("Devices and sensors initialized with proper relationships")
        except Exception as e:
            session.rollback()
            logger.error(f"Device/sensor initialization failed: {e}")
            raise

def initialize_all_data():
    """Initialize all default data (rooms, options, scenarios)."""
    logger.info("Entering initialize_all_data() function")
    try:
        initialize_options()
        initialize_rooms()
        initialize_devices_and_sensors()
        
        # Initialize scenarios with a dedicated session
        with db_session() as session:
            initialize_scenarios()
            
        logger.info("Exiting initialize_all_data() function")
    except Exception as e:
        logger.exception("Exception during initialize_all_data:")
        raise

if __name__ == "__main__":
    initialize_all_data() 