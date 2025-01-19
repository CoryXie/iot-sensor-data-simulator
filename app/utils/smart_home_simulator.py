import random
from datetime import datetime
from typing import Dict

class SmartHomeSimulator:
    """Class to handle smart home sensor value simulation"""
    
    def __init__(self):
        self.current_scenario = None
        self.scenario_start_time = None
        self.base_values = {}
        
    def set_scenario(self, scenario_name: str):
        """Set the current scenario for simulation"""
        self.current_scenario = scenario_name
        self.scenario_start_time = datetime.now()
        self.base_values = {}
        
    def adjust_sensor_value(self, base_value: float, sensor_type: int) -> float:
        """Adjust a sensor value based on the current scenario and time"""
        if sensor_type not in self.base_values:
            self.base_values[sensor_type] = base_value
            
        # Get time-based variation
        time_variation = self._get_time_variation(sensor_type)
        
        # Get scenario-based variation
        scenario_variation = self._get_scenario_variation(sensor_type)
        
        # Add some random noise
        noise = random.uniform(-0.5, 0.5)
        
        # Combine all variations
        adjusted_value = self.base_values[sensor_type] + time_variation + scenario_variation + noise
        
        # Ensure the value stays within reasonable bounds
        return max(0, adjusted_value)
    
    def _get_time_variation(self, sensor_type: int) -> float:
        """Get time-based variation for a sensor type"""
        current_hour = datetime.now().hour
        
        # Temperature varies throughout the day
        if sensor_type == 0:  # Temperature
            if 0 <= current_hour < 6:  # Night
                return -2.0
            elif 6 <= current_hour < 12:  # Morning
                return 0.0
            elif 12 <= current_hour < 18:  # Afternoon
                return 2.0
            else:  # Evening
                return 0.0
        
        # Light level varies with time
        elif sensor_type == 14:  # Brightness
            if 6 <= current_hour < 18:  # Daytime
                return 50.0
            else:  # Nighttime
                return -30.0
        
        # Motion more likely during day
        elif sensor_type == 22:  # Motion
            if 8 <= current_hour < 22:  # Active hours
                return 0.3
            else:  # Quiet hours
                return -0.3
                
        return 0.0
    
    def _get_scenario_variation(self, sensor_type: int) -> float:
        """Get scenario-based variation for a sensor type"""
        if not self.current_scenario:
            return 0.0
            
        # Example scenarios and their effects
        scenarios = {
            'Normal Day': {
                0: 0.0,    # Normal temperature
                14: 0.0,   # Normal light
                22: 0.0    # Normal motion
            },
            'Hot Day': {
                0: 5.0,    # Higher temperature
                14: 10.0,  # Brighter
                22: -0.1   # Slightly less motion
            },
            'Cold Night': {
                0: -5.0,   # Lower temperature
                14: -20.0, # Darker
                22: -0.2   # Less motion
            },
            'Party Mode': {
                0: 2.0,    # Slightly higher temperature
                14: 20.0,  # Much brighter
                22: 0.5    # More motion
            },
            'Away Mode': {
                0: -1.0,   # Slightly lower temperature
                14: -30.0, # Darker
                22: -0.4   # Much less motion
            },
            'Morning': {
                0: -2.0,   # Cooler morning temperature
                14: 5.0,   # Gradually brightening
                22: 0.2    # Increasing motion
            }
        }
        
        if self.current_scenario in scenarios:
            return scenarios[self.current_scenario].get(sensor_type, 0.0)
            
        return 0.0 