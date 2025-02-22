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

def initialize_scenarios():
    """Initialize scenarios with multi-room support"""
    with db_session() as session:
        try:
            # Clear existing data
            session.query(Container).delete()
            session.query(Scenario).delete()
            
            # Track existing devices to avoid duplicates
            existing_devices = {
                (d.room.name, d.name.replace(d.room.name + " ", "")): d
                for d in session.query(Device).all()
            }
            
            for scenario_name, template in SCENARIO_TEMPLATES.items():
                # Validate template structure
                required_fields = ['type', 'description', 'devices']
                if not all(field in template for field in required_fields):
                    missing = [f for f in required_fields if f not in template]
                    logger.error(f"Scenario '{scenario_name}' missing required fields: {', '.join(missing)}")
                    continue
                
                # Handle both new and legacy template formats
                rooms = template.get('rooms', [])
                if 'room_type' in template:  # Legacy support
                    rooms = [template['room_type']]
                
                if not rooms:
                    logger.error(f"Scenario '{scenario_name}' has no rooms defined")
                    continue
                
                # Create scenario
                scenario = Scenario(
                    name=scenario_name,
                    scenario_type=template['type'],
                    description=template['description']
                )
                session.add(scenario)
                session.flush()

                # Create containers for each room in the scenario
                for room_type in rooms:
                    room = session.query(Room).filter_by(room_type=room_type).first()
                    if not room:
                        logger.error(f"Room type {room_type} not found for scenario {scenario_name}")
                        continue
                    
                    # Create room-specific container with UUID for uniqueness
                    container = Container(
                        name=f"{scenario_name} - {room.name} - {str(uuid.uuid4())[:8]}",
                        description=f"{scenario_name} in {room.name}",
                        location=room.name,
                        scenario=scenario
                    )
                    session.add(container)
                    session.flush()

                    # Create or reuse devices for this room-container combination
                    for device_template in template['devices']:
                        # Support both new and legacy device formats
                        device_name = device_template.get('device') or device_template.get('name')
                        device_type = DEVICE_TEMPLATES.get(device_name, {}).get('type')
                        
                        if not device_type:
                            logger.error(f"Invalid device template: {device_name}")
                            continue
                        
                        # Check if device belongs in this room
                        device_rooms = device_template.get('rooms', [])
                        if 'room_type' in device_template:  # Legacy support
                            device_rooms = [device_template['room_type']]
                        
                        if device_rooms and room_type not in device_rooms:
                            continue
                        
                        # Check if device already exists
                        device_key = (room.name, device_name)
                        if device_key in existing_devices:
                            # Update container reference for existing device
                            device = existing_devices[device_key]
                            device.container = container
                            session.add(device)
                        else:
                            # Create new device
                            device = Device(
                                name=f"{room.name} {device_name}",
                                type=device_type,
                                room=room,
                                container=container
                            )
                            session.add(device)
                            session.commit()
                            existing_devices[device_key] = device
                
                logger.debug(f"Created scenario '{scenario_name}' spanning {len(rooms)} rooms")
            
            session.commit()
            logger.success("Multi-room scenarios initialized successfully")
        except Exception as e:
            session.rollback()
            logger.error(f"Scenario initialization failed: {e}")
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
    with SessionLocal() as session:
        try:
            # Clear existing data
            session.query(Sensor).delete()
            session.query(Device).delete()
            
            # Track created devices to avoid duplicates
            created_devices = {}  # (room_name, device_name) -> device
            
            for room_name, template in ROOM_TEMPLATES.items():
                room = session.query(Room).filter_by(name=room_name).first()
                if not room:
                    logger.error(f"Room {room_name} not found during device initialization")
                    continue
                
                for device_name in template['devices']:
                    device_template = DEVICE_TEMPLATES[device_name]
                    device_key = (room_name, device_name)
                    
                    # Skip if device already exists for this room
                    if device_key in created_devices:
                        continue
                        
                    # Create device with explicit room assignment
                    device = Device(
                        name=f"{room_name} {device_name}",
                        type=device_template['type'],
                        room=room  # Direct relationship assignment
                    )
                    session.add(device)
                    session.commit()  # Generate ID before accessing
                    session.flush()  # Ensure device ID is generated
                    
                    # Store reference to created device
                    created_devices[device_key] = device
                    
                    logger.debug(f"Created device {device.name} (ID: {device.id}) "
                                f"in room {room.name} (ID: {room.id})")
                    
                    # Create sensors
                    for sensor_template in device_template['sensors']:
                        sensor = Sensor(
                            name=sensor_template['name'],
                            type=sensor_template['type'],
                            unit=sensor_template.get('unit'),
                            device=device,  # Direct device assignment
                            room=room      # Explicit room assignment
                        )
                        session.add(sensor)
                        logger.debug(f"Created sensor {sensor.name} (ID: None) "
                                    f"for device {device.name}")
            
            session.commit()
            logger.success("Devices and sensors initialized with proper relationships")
        except Exception as e:
            session.rollback()
            logger.error(f"Device and sensor initialization failed: {e}")
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