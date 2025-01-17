from datetime import datetime, time
from constants.device_templates import TIME_PATTERNS, SCENARIO_TEMPLATES
import math
import random

class SmartHomeSimulator:
    """Helper class for smart home simulation patterns"""

    def __init__(self):
        self.current_scenario = "Home"
        self.time_of_day = "day"

    def get_time_of_day(self, current_time=None):
        """Determine the time of day based on current hour"""
        if current_time is None:
            current_time = datetime.now().time()
        
        if time(22,0) <= current_time or current_time <= time(5,0):
            return "night"
        elif time(5,0) <= current_time <= time(11,0):
            return "morning"
        elif time(11,0) <= current_time <= time(17,0):
            return "day"
        else:
            return "evening"

    def adjust_sensor_value(self, base_value, sensor_type, current_time=None):
        """Adjust sensor value based on time of day and current scenario"""
        time_of_day = self.get_time_of_day(current_time)
        scenario = SCENARIO_TEMPLATES[self.current_scenario]
        
        # Temperature adjustment
        if sensor_type == 0:  # Temperature
            time_pattern = TIME_PATTERNS["temperature"][time_of_day]
            scenario_adj = scenario["sensor_adjustments"]["temperature"]
            
            adjusted_value = base_value + time_pattern["offset"] + scenario_adj["offset"]
            variation = random.uniform(-time_pattern["variation"], time_pattern["variation"])
            return adjusted_value + variation
        
        # Motion sensor adjustment
        elif sensor_type == 22:  # Motion
            base_probability = TIME_PATTERNS["occupancy"][time_of_day]["probability"]
            scenario_probability = scenario["sensor_adjustments"]["motion"]["probability"]
            return 1 if random.random() < (base_probability * scenario_probability) else 0
        
        # Energy consumption adjustment
        elif sensor_type == 28:  # Energy Consumption
            time_factor = TIME_PATTERNS["energy"][time_of_day]["factor"]
            scenario_factor = scenario["sensor_adjustments"]["energy"]["factor"]
            variation = random.uniform(-0.1, 0.1)
            return base_value * time_factor * scenario_factor * (1 + variation)
        
        # Default: return original value with small random variation
        return base_value * (1 + random.uniform(-0.05, 0.05))

    def set_scenario(self, scenario_name):
        """Set the current home scenario"""
        if scenario_name in SCENARIO_TEMPLATES:
            self.current_scenario = scenario_name
            return True
        return False

    def get_correlated_values(self, primary_value, primary_type, secondary_type):
        """Generate correlated sensor values"""
        if primary_type == 0 and secondary_type == 8:  # Temperature -> Humidity
            # Higher temperature generally means lower humidity
            return max(30, min(70, 100 - (primary_value * 1.5)))
        
        elif primary_type == 22 and secondary_type == 14:  # Motion -> Brightness
            # Motion might trigger lights
            if primary_value == 1:
                return random.uniform(200, 800)  # Lights on
            return random.uniform(0, 50)  # Lights off or ambient light
        
        elif primary_type == 0 and secondary_type == 35:  # Temperature -> Thermal Comfort
            # Comfort index drops as temperature deviates from ideal (22°C)
            deviation = abs(primary_value - 22)
            return max(0, min(100, 100 - (deviation * 5)))
        
        return None  # No correlation defined 