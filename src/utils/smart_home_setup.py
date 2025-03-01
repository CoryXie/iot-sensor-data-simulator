from typing import Dict, List, Optional
from src.models.sensor import Sensor
from src.models.device import Device
from src.models.container import Container
from src.constants.units import UNITS
from src.constants.device_templates import DEVICE_TEMPLATES, SCENARIO_TEMPLATES, ROOM_TYPES, ROOM_TEMPLATES
from src.constants.units import UNITS
import logging
from src.database import db_session, SessionLocal
from loguru import logger
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

def get_unit_id_by_name(unit_name: str) -> Optional[int]:
    """
    Helper function to get unit ID by unit name.
    """
    for unit in UNITS:
        if unit['name'] == unit_name:
            return unit['id']
    return None

class SmartHomeSetup:
    """Utility class for setting up smart home scenarios"""

    def __init__(self):
        pass

    def get_unit_id_by_name(self, unit_name: str) -> Optional[int]:
        """
        Helper function to get unit ID by unit name.
        """
        for unit in UNITS:
            if unit['name'] == unit_name:
                return unit['id']
        return None
        self.active_scenario = None
        self.scenario_states = {}  # Store states for each scenario

    def save_scenario_state(self, scenario_name: str):
        """Save the current state of a scenario's devices and sensors"""
        try:
            container = Container.get_by_name(f"Smart Home - {scenario_name}")
            if not container:
                return

            state = {
                'container_id': container.id,
                'devices': []
            }

            for device in container.devices:
                device_state = {
                    'device_id': device.id,
                    'sensors': []
                }
                for sensor in device.sensors:
                    sensor_state = {
                        'sensor_id': sensor.id,
                        'last_value': sensor.last_value,
                        'error_definition': sensor.error_definition
                    }
                    device_state['sensors'].append(sensor_state)
                state['devices'].append(device_state)

            self.scenario_states[scenario_name] = state

        except Exception as e:
            print(f"Error saving scenario state: {str(e)}")

    def restore_scenario_state(self, scenario_name: str):
        """Restore a previously saved scenario state"""
        try:
            if scenario_name not in self.scenario_states:
                return

            state = self.scenario_states[scenario_name]
            container = Container.get_by_id(state['container_id'])
            if not container:
                return

            for device_state in state['devices']:
                device = Device.get_by_id(device_state['device_id'])
                if not device:
                    continue

                for sensor_state in device_state['sensors']:
                    sensor = Sensor.get_by_id(sensor_state['sensor_id'])
                    if not sensor:
                        continue
                    sensor.last_value = sensor_state['last_value']
                    sensor.error_definition = sensor_state['error_definition']
                    sensor.save()

        except Exception as e:
            print(f"Error restoring scenario state: {str(e)}")

    def deactivate_current_scenario(self):
        """Deactivate the currently active scenario"""
        try:
            if self.active_scenario:
                # Save current state before deactivating
                self.save_scenario_state(self.active_scenario)

                # Stop the container
                container = Container.get_by_name(f"Smart Home - {self.active_scenario}")
                if container and container.is_active:
                    container.stop()

                self.active_scenario = None
                return True
            return False

        except Exception as e:
            print(f"Error deactivating scenario: {str(e)}")
            return False

    def activate_scenario(self, scenario_name: str) -> Optional[Container]:
        """Activate a scenario, deactivating any currently active scenario"""
        session = db_session()
        try:
            # First, deactivate current scenario if any
            if not self.deactivate_current_scenario():
                logger.warning("Failed to deactivate current scenario")
                return None

            if scenario_name not in SCENARIO_TEMPLATES:
                logger.warning(f"Unknown scenario: {scenario_name}")
                return None

            # Create or get the container for this scenario
            container = session.query(Container).filter_by(name=f"Smart Home - {scenario_name}").first()
            if not container:
                container = self.create_scenario(scenario_name)
                if not container:
                    return None

            # Ensure the container is in the current session
            container = session.merge(container)
            
            # Restore previous state if exists
            self.restore_scenario_state(scenario_name)

            # Start the container
            container.start(session)
            session.commit()
            
            self.active_scenario = scenario_name

            return container

        except Exception as e:
            session.rollback()
            logger.error(f"Error activating scenario: {str(e)}")
            return None
        finally:
            session.close()

    def create_scenario(self, scenario_name: str) -> Container:
        """Create a new scenario with devices and sensors"""
        try:
            logger.info(f"Creating new scenario: {scenario_name}")
            
            with db_session() as session:
                # Create container
                container = Container(
                    name=f"Smart Home - {scenario_name}",
                    description=f"Smart home setup for {scenario_name}",
                    container_type="smart_home",
                    is_active=False
                )
                session.add(container)
                session.flush()  # Get container ID
                
                # Create devices and sensors for each room
                for room_type in ROOM_TYPES:
                    if room_type in ROOM_TEMPLATES:
                        room_template = ROOM_TEMPLATES[room_type]
                        
                        # Create devices for this room
                        for device_type in room_template['devices']:
                            if device_type in DEVICE_TEMPLATES:
                                device_template = DEVICE_TEMPLATES[device_type]
                                
                                # Create device
                                device = Device(
                                    name=f"{room_type} {device_type}",
                                    type=device_type,
                                    location=room_type,
                                    container_id=container.id,
                                    description=device_template['description']
                                )
                                session.add(device)
                                session.flush()  # Get device ID
                                
                                # Create sensors for this device
                                for sensor_template in device_template['sensors']:
                                    sensor = Sensor(
                                        name=sensor_template['name'],
                                        type=sensor_template['type'],
                                        device_id=device.id,
                                        unit=sensor_template['unit'],
                                        min_value=sensor_template['min'],
                                        max_value=sensor_template['max'],
                                        current_value=sensor_template['min'],
                                        base_value=sensor_template['min'],
                                        variation_range=sensor_template.get('variation', 1.0),
                                        change_rate=sensor_template.get('change_rate', 0.1),
                                        interval=sensor_template.get('interval', 5)
                                    )
                                    session.add(sensor)
                
                session.commit()
                # Refresh the container to ensure all relationships are loaded
                session.refresh(container)
                logger.info(f"Successfully created scenario: {scenario_name}")
                return container
                
        except Exception as e:
            logger.error(f"Error creating scenario: {str(e)}")
            raise

    def cleanup_scenario(self, scenario_name: str):
        """Clean up all components of a scenario"""
        try:
            with db_session() as session:
                container = session.query(Container).filter_by(
                    name=f"Smart Home - {scenario_name}"
                ).first()
                
                if container:
                    # Refresh within the same session
                    session.refresh(container)

                    # Stop if active
                    if container.is_active:
                        container.stop()
                        if self.active_scenario == scenario_name:
                            self.active_scenario = None

                    # Delete the container (this will cascade to devices and sensors)
                    session.delete(container)
                    session.commit()

                # Remove saved state
                if scenario_name in self.scenario_states:
                    del self.scenario_states[scenario_name]

        except Exception as e:
            logger.error(f"Error cleaning up scenario: {str(e)}")
            raise

    def get_active_scenario(self) -> Optional[str]:
        """Get the name of the currently active scenario"""
        return self.active_scenario

    def list_scenarios(self):
        """List all available scenarios"""
        try:
            session = db_session()
            containers = session.query(Container).options(
                joinedload(Container.scenario),
                joinedload(Container.devices)
                .joinedload(Device.sensors)
            ).all()
            
            scenarios = []
            for container in containers:
                scenario = {
                    'id': container.id,
                    'name': container.name,
                    'description': container.description,
                    'type': container.container_type,
                    'device_count': len(container.devices),
                    'sensor_count': sum(len(d.sensors) for d in container.devices),
                    'is_template': False,
                    'is_active': container.is_active
                }
                scenarios.append(scenario)
            
            # Add template scenarios
            for name, template in SCENARIO_TEMPLATES.items():
                # Calculate total device count across all containers
                device_count = sum(len(container.get('devices', [])) for container in template.get('containers', []))
                
                # Calculate total sensor count for all devices across all containers
                sensor_count = 0
                for container in template.get('containers', []):
                    for device_info in container.get('devices', []):
                        device_type = device_info.get('device_type')
                        if device_type in DEVICE_TEMPLATES:
                            sensor_count += len(DEVICE_TEMPLATES[device_type]['sensors'])
                
                scenarios.append({
                    'id': None,
                    'name': name,
                    'description': template['description'],
                    'type': template['type'],
                    'device_count': device_count,
                    'sensor_count': sensor_count,
                    'is_template': True,
                    'is_active': False
                })
                
            return sorted(scenarios, key=lambda x: x['name'])
        
        except Exception as e:
            logger.error(f"Error listing scenarios: {str(e)}")
            return []