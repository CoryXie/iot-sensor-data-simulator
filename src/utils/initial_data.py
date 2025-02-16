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

def initialize_rooms():
    """Initialize rooms with proper session handling"""
    with db_session() as session:
        try:
            logger.info("Initializing rooms...")
            for room_name, room_data in ROOM_TEMPLATES.items():
                if not session.query(Room).filter_by(name=room_name).first():
                    logger.debug(f"Creating room: {room_name}")
                    session.add(Room(
                        name=room_name,
                        room_type=room_data['room_type'],
                        description=room_data['description']
                    ))
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

def initialize_scenarios(session):
    """Initialize default scenarios from templates"""
    try:
        logger.info("Initializing scenarios from templates...")
        for name, template in SCENARIO_TEMPLATES.items():
            scenario = session.query(Scenario).filter_by(name=name).first()
            
            if not scenario:
                scenario = Scenario(
                    name=name,
                    description=template['description'],
                    scenario_type=template['type'],
                    is_active=template['is_active']
                )
                session.add(scenario)
                logger.debug(f"Created new scenario: {name}")

            # Update existing scenarios with template data
            scenario.description = template['description']
            scenario.scenario_type = template['type']
            
            # Create container relationship if missing
            if not scenario.container:
                container = Container(
                    name=f"{name} Container",
                    container_type="scenario",
                    is_active=False
                )
                session.add(container)
                scenario.container = container
            
            session.flush()
        
        session.commit()
        logger.success("Scenarios initialized from templates")
    except Exception as e:
        session.rollback()
        logger.error(f"Error initializing scenarios: {str(e)}")
        raise

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
    """Initialize devices and sensors from templates"""
    with db_session() as session:
        try:
            logger.info("Initializing devices and sensors...")
            
            # Create devices from templates
            for device_name, template in DEVICE_TEMPLATES.items():
                # Find or create device
                device = session.query(Device).filter_by(name=device_name).first()
                if not device:
                    logger.debug(f"Creating device: {device_name}")
                    device = Device(
                        name=device_name,
                        type=template['type'],
                        description=template['description'],
                        icon=template['icon']
                    )
                    session.add(device)
                    session.flush()  # Get device ID for sensors

                # Create sensors for this device
                for sensor_template in template['sensors']:
                    sensor = session.query(Sensor).filter_by(
                        device_id=device.id,
                        name=sensor_template['name']
                    ).first()
                    
                    if not sensor:
                        logger.debug(f"Creating sensor: {sensor_template['name']} for {device_name}")
                        session.add(Sensor(
                            name=sensor_template['name'],
                            type=sensor_template['type'],
                            device=device,
                            unit=sensor_template['unit'],
                            min_value=sensor_template['min'],
                            max_value=sensor_template['max'],
                            current_value=sensor_template.get('base', sensor_template['min']),
                            base_value=sensor_template.get('base', sensor_template['min']),
                            variation_range=sensor_template['variation'],
                            change_rate=sensor_template['change_rate'],
                            interval=sensor_template['interval']
                        ))

            session.commit()
            logger.success("Devices and sensors initialized successfully")
            
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
            initialize_scenarios(session)
            
        logger.info("Exiting initialize_all_data() function")
    except Exception as e:
        logger.exception("Exception during initialize_all_data:")
        raise

if __name__ == "__main__":
    initialize_all_data() 