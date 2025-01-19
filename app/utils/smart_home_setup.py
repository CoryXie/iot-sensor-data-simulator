from typing import Dict, List, Optional
from models.sensor import Sensor
from models.device import Device
from models.container import Container
from constants.device_templates import DEVICE_TEMPLATES, SCENARIO_TEMPLATES, ROOM_TYPES
from constants.units import UNITS

class SmartHomeSetup:
    """Utility class for setting up smart home scenarios"""
    
    def __init__(self):
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
        try:
            # First, deactivate current scenario if any
            if not self.deactivate_current_scenario():
                print("Failed to deactivate current scenario")
                return None
            
            if scenario_name not in SCENARIO_TEMPLATES:
                print(f"Unknown scenario: {scenario_name}")
                return None
            
            # Create or get the container for this scenario
            container = Container.get_by_name(f"Smart Home - {scenario_name}")
            if not container:
                container = self.create_scenario(scenario_name)
                if not container:
                    return None
                
                # Ensure the container is persisted
                container.save()
            
            # Refresh to ensure we have the latest state
            container.refresh()
            
            # Restore previous state if exists
            self.restore_scenario_state(scenario_name)
            
            # Start the container
            container.start()
            self.active_scenario = scenario_name
            
            return container
            
        except Exception as e:
            print(f"Error activating scenario: {str(e)}")
            return None
            
    def create_scenario(self, scenario_name: str) -> Container:
        """Create a new scenario with the given name"""
        if scenario_name not in SCENARIO_TEMPLATES:
            print(f"Unknown scenario: {scenario_name}")
            return None
            
        scenario = SCENARIO_TEMPLATES[scenario_name]
        container_name = f"Smart Home - {scenario_name}"
        
        # First try to find existing container
        existing_container = Container.get_by_name(container_name)
        if existing_container:
            # Stop and delete the existing container
            existing_container.stop()
            existing_container.delete()
            
        # Create new container
        try:
            container = Container.add(
                name=container_name,
                description=scenario.get('description', ''),
                location='Smart Home'
            )
            
            if not container:
                print(f"Failed to create container for scenario: {scenario_name}")
                return None
                
            # Create devices for each room type
            for room_type in ROOM_TYPES:
                if 'devices' in scenario:
                    for device_type in scenario['devices']:
                        if device_type in DEVICE_TEMPLATES:
                            device_template = DEVICE_TEMPLATES[device_type]
                            device_name = f"{room_type} - {device_type}"
                            
                            # Create device
                            device = Device.add(
                                device_name=device_name,
                                container_id=container.id
                            )
                            
                            if not device:
                                print(f"Failed to create device: {device_name}")
                                continue
                                
                            # Create sensors for the device
                            if 'sensors' in device_template:
                                for sensor_template in device_template['sensors']:
                                    # Calculate base value as midpoint between min and max
                                    min_val = sensor_template.get('min', 0)
                                    max_val = sensor_template.get('max', 100)
                                    base_value = (min_val + max_val) / 2
                                    
                                    sensor = Sensor.add(
                                        name=sensor_template['name'],
                                        device_id=device.id,
                                        unit=sensor_template['unit'],
                                        base_value=base_value,
                                        variation_range=sensor_template.get('variation', 1.0),
                                        change_rate=sensor_template.get('change_rate', 0.1),
                                        interval=sensor_template.get('interval', 5)
                                    )
                                    if not sensor:
                                        print(f"Failed to create sensor: {sensor_template['name']}")
                        else:
                            print(f"Unknown device type: {device_type}")
                            
            return container
            
        except Exception as e:
            print(f"Error creating scenario: {str(e)}")
            import traceback
            print(traceback.format_exc())
            # If container was created but failed to add devices, clean it up
            if container:
                container.delete()
            return None
            
    def cleanup_scenario(self, scenario_name: str):
        """Clean up all components of a scenario"""
        try:
            container = Container.get_by_name(f"Smart Home - {scenario_name}")
            if container:
                # Refresh to ensure we have the latest state
                container.refresh()
                
                # Stop if active
                if container.is_active:
                    container.stop()
                    if self.active_scenario == scenario_name:
                        self.active_scenario = None
                
                # Delete the container (this will cascade to devices and sensors)
                container.delete()
                
            # Remove saved state
            if scenario_name in self.scenario_states:
                del self.scenario_states[scenario_name]
                
        except Exception as e:
            print(f"Error cleaning up scenario: {str(e)}")
    
    def get_active_scenario(self) -> Optional[str]:
        """Get the name of the currently active scenario"""
        return self.active_scenario
    
    def list_scenarios(self) -> List[Dict]:
        """List all available scenarios with their current status"""
        try:
            scenarios = []
            for name, template in SCENARIO_TEMPLATES.items():
                container = Container.get_by_name(f"Smart Home - {name}")
                scenario_info = {
                    'id': container.id if container else None,
                    'name': name,
                    'description': template['description'],
                    'device_count': len(container.devices) if container else 0,
                    'sensor_count': sum(len(device.sensors) for device in container.devices) if container else 0,
                    'is_active': container.is_active if container else False
                } if container else {
                    'id': None,
                    'name': name,
                    'description': template['description'],
                    'device_count': 0,
                    'sensor_count': 0,
                    'is_active': False
                }
                scenarios.append(scenario_info)
            return scenarios
        except Exception as e:
            print(f"Error listing scenarios: {str(e)}")
            return [] 