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
                required_fields = ['type', 'description', 'containers']
                if not all(field in template for field in required_fields):
                    missing = [f for f in required_fields if f not in template]
                    logger.error(f"Scenario '{scenario_name}' missing required fields: {', '.join(missing)}")
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
                for container_info in template['containers']:
                    room_type = container_info.get('room_type')
                    if not room_type:
                        logger.error(f"Container missing room_type in scenario {scenario_name}")
                        continue
                    
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
                    for device_info in container_info.get('devices', []):
                        device_type = device_info.get('device_type')
                        if not device_type or device_type not in DEVICE_TEMPLATES:
                            logger.error(f"Invalid device type: {device_type} in scenario {scenario_name}")
                            continue
                        
                        # Check if device already exists
                        device_key = (room.name, device_type)
                        if device_key in existing_devices:
                            # Update container reference for existing device
                            device = existing_devices[device_key]
                            device.container = container
                            session.add(device)
                        else:
                            # Create new device
                            device = Device(
                                name=f"{room.name} {device_type}",
                                type=DEVICE_TEMPLATES[device_type]['type'],
                                room=room,
                                container=container
                            )
                            session.add(device)
                            session.commit()
                            existing_devices[device_key] = device
                
                logger.debug(f"Created scenario '{scenario_name}' with {len(template['containers'])} containers")
            
            session.commit()
            logger.success("Multi-room scenarios initialized successfully")
        except Exception as e:
            session.rollback()
            logger.error(f"Scenario initialization failed: {e}")
            raise

def initialize_options():
    """Initialize default options if not already set"""
    with SessionLocal() as session:
        try:
            logger.info("Initializing default options...")
            
            # Only set demo_mode if it doesn't exist
            if Option.get_value('demo_mode') is None:
                Option.set_value('demo_mode', 'false')
                logger.debug("Setting default option: demo_mode = false")
                
            if not Option.get_value('mqtt_enabled'):
                Option.set_value('mqtt_enabled', 'true')
                logger.debug("Setting default option: mqtt_enabled = true")
                
            if not Option.get_value('simulation_interval'):
                Option.set_value('simulation_interval', '5')
                logger.debug("Setting default option: simulation_interval = 5")
                
            session.commit()
            logger.success("Default options initialized.")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Option initialization failed: {e}")
            raise

def initialize_devices_and_sensors():
    """Initialize smart home devices and their sensors"""
    with db_session() as session:
        try:
            logger.info("Initializing devices and sensors...")
            rooms = session.query(Room).all()
            
            if not rooms:
                logger.warning("No rooms found! Please initialize rooms first.")
                return
            
            # Check if whole home AC exists
            whole_home_ac = session.query(Device).filter_by(type='hvac_system').first()
            
            # Check if living room exists
            living_room = next((room for room in rooms if room.room_type == 'living_room'), None)
            if living_room and not whole_home_ac:
                # Add whole home AC (once)
                whole_home_ac = Device(
                    name="Whole Home AC",
                    type="hvac_system",
                    description="Central air conditioning system",
                    icon="mdi-air-conditioner",
                    room=living_room
                )
                session.add(whole_home_ac)
                
                # Add sensors to AC
                for sensor_data in DEVICE_TEMPLATES['Whole Home AC']['sensors']:
                    sensor = Sensor(
                        name=sensor_data['name'],
                        type=sensor_data['type'],
                        unit=sensor_data['unit'],
                        min_value=sensor_data['min_value'],
                        max_value=sensor_data['max_value'],
                        device=whole_home_ac
                    )
                    # Set default values
                    if sensor.type == 'power':
                        sensor.current_value = 0  # Off by default
                    elif sensor.type == 'set_temperature':
                        sensor.current_value = 22.0  # Default temperature
                    elif sensor.type == 'mode':
                        sensor.current_value = 0  # Auto mode
                    elif sensor.type == 'fan_speed':
                        sensor.current_value = 3  # Medium speed
                    
                    session.add(sensor)
                
                logger.info(f"Added whole home AC system to {living_room.name}")
            
            # Add a thermostat to each bedroom if it doesn't exist
            for room in rooms:
                if room.room_type == 'bedroom' and not session.query(Device).filter_by(type='thermostat', room_id=room.id).first():
                    # Add thermostat
                    thermostat = Device(
                        name=f"{room.name} Thermostat",
                        type="thermostat",
                        description="Smart room temperature control",
                        icon="mdi-thermostat",
                        room=room
                    )
                    session.add(thermostat)
                    
                    # Add sensors to thermostat
                    for sensor_data in DEVICE_TEMPLATES['Smart Thermostat']['sensors']:
                        sensor = Sensor(
                            name=sensor_data['name'],
                            type=sensor_data['type'],
                            unit=sensor_data['unit'],
                            min_value=sensor_data['min_value'],
                            max_value=sensor_data['max_value'],
                            device=thermostat
                        )
                        # Set default values
                        if sensor.type == 'power':
                            sensor.current_value = 0  # Off by default
                        elif sensor.type == 'set_temperature':
                            sensor.current_value = 22.0  # Default temperature
                        elif sensor.type == 'mode':
                            sensor.current_value = 0  # Auto mode
                        
                        session.add(sensor)
                    
                    logger.info(f"Added thermostat to {room.name}")
                
                # Add smart blinds to living room, bedrooms and office
                if room.room_type in ['living_room', 'bedroom', 'office'] and not session.query(Device).filter_by(type='blinds', room_id=room.id).first():
                    # Add blinds
                    blinds = Device(
                        name=f"{room.name} Smart Blinds",
                        type="blinds",
                        description="Automated window blinds",
                        icon="mdi-blinds",
                        room=room
                    )
                    session.add(blinds)
                    
                    # Add sensors to blinds
                    for sensor_data in DEVICE_TEMPLATES['Smart Blinds']['sensors']:
                        sensor = Sensor(
                            name=sensor_data['name'],
                            type=sensor_data['type'],
                            unit=sensor_data['unit'],
                            min_value=sensor_data['min_value'],
                            max_value=sensor_data['max_value'],
                            device=blinds
                        )
                        # Set default values
                        if sensor.type == 'position':
                            sensor.current_value = 50  # Half open by default
                        elif sensor.type == 'mode':
                            sensor.current_value = 0  # Manual mode
                        
                        session.add(sensor)
                    
                    logger.info(f"Added smart blinds to {room.name}")
                
            # Find if there's a garden/patio/outdoor space
            outdoor_room = next((room for room in rooms if not room.is_indoor), None)
            if outdoor_room and not session.query(Device).filter_by(type='irrigation', room_id=outdoor_room.id).first():
                # Add irrigation system
                irrigation = Device(
                    name=f"{outdoor_room.name} Irrigation",
                    type="irrigation",
                    description="Automated garden watering system",
                    icon="mdi-water-pump",
                    room=outdoor_room
                )
                session.add(irrigation)
                
                # Add sensors to irrigation system
                for sensor_data in DEVICE_TEMPLATES['Smart Irrigation']['sensors']:
                    sensor = Sensor(
                        name=sensor_data['name'],
                        type=sensor_data['type'],
                        unit=sensor_data['unit'],
                        min_value=sensor_data['min_value'],
                        max_value=sensor_data['max_value'],
                        device=irrigation
                    )
                    # Set default values
                    if sensor.type == 'moisture':
                        sensor.current_value = 40  # Default moisture
                    elif sensor.type == 'flow':
                        sensor.current_value = 0  # No flow by default
                    elif sensor.type == 'schedule':
                        sensor.current_value = 0  # No schedule by default
                    
                    session.add(sensor)
                
                logger.info(f"Added irrigation system to {outdoor_room.name}")
            
            # Add standard devices to rooms that don't have them yet
            for room in rooms:
                for device_name in ROOM_TEMPLATES.get(room.name, {}).get('devices', []):
                    # Check if device already exists in this room
                    existing_device = session.query(Device).filter_by(
                        name=f"{room.name} {device_name}", 
                        room_id=room.id
                    ).first()
                    
                    if not existing_device:
                        # Get device template
                        device_template = DEVICE_TEMPLATES.get(device_name)
                        if not device_template:
                            logger.warning(f"No template found for device: {device_name}")
                            continue
                        
                        # Create device
                        device = Device(
                            name=f"{room.name} {device_name}",
                            type=device_template['type'],
                            description=device_template['description'],
                            icon=device_template.get('icon', 'mdi-devices'),
                            room=room
                        )
                        session.add(device)
                        logger.info(f"Added device {device.name} to {room.name}")
                        
                        # Create sensors for device
                        for sensor_template in device_template.get('sensors', []):
                            sensor = Sensor(
                                name=sensor_template['name'],
                                type=sensor_template['type'],
                                unit=sensor_template.get('unit', ''),
                                min_value=sensor_template.get('min_value', 0),
                                max_value=sensor_template.get('max_value', 100),
                                device=device,
                                room=room
                            )
                            session.add(sensor)
                            logger.debug(f"Added sensor {sensor.name} to {device.name}")
            
            session.commit()
            logger.success("Successfully initialized devices and sensors")
        except Exception as e:
            session.rollback()
            logger.error(f"Error initializing devices and sensors: {e}")

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