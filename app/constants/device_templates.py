# Description: Templates for common smart home devices
# Each template defines a set of sensors and their default configurations

ROOM_TYPES = [
    "Living Room",
    "Kitchen",
    "Bedroom",
    "Bathroom",
    "Garage",
    "Outdoor",
    "Basement"
]

DEVICE_TEMPLATES = {
    "Environmental Monitor": {
        "description": "Monitors indoor environmental conditions",
        "sensors": [
            {"type": 0, "name": "Room Temperature", "min": 15, "max": 30},  # Temperature
            {"type": 8, "name": "Room Humidity", "min": 30, "max": 70},     # Humidity
            {"type": 17, "name": "CO2 Level", "min": 400, "max": 2000},     # CO2
            {"type": 18, "name": "VOC Level", "min": 0, "max": 2000},       # VOC
            {"type": 14, "name": "Room Light", "min": 0, "max": 1000}       # Brightness
        ]
    },
    "Security System": {
        "description": "Comprehensive security monitoring",
        "sensors": [
            {"type": 22, "name": "Motion Sensor", "min": 0, "max": 1},      # Motion
            {"type": 23, "name": "Door Contact", "min": 0, "max": 1},       # Contact
            {"type": 24, "name": "Glass Break", "min": 0, "max": 1},        # Glass Break
            {"type": 25, "name": "Smoke Detector", "min": 0, "max": 100},   # Smoke
            {"type": 26, "name": "CO Detector", "min": 0, "max": 50}        # Carbon Monoxide
        ]
    },
    "Energy Monitor": {
        "description": "Tracks energy consumption and generation",
        "sensors": [
            {"type": 28, "name": "Power Usage", "min": 0, "max": 10000},    # Energy Consumption
            {"type": 31, "name": "Solar Generation", "min": 0, "max": 5000}, # Solar Output
            {"type": 32, "name": "Battery Status", "min": 0, "max": 100},    # Battery Level
            {"type": 9, "name": "Grid Voltage", "min": 220, "max": 240},     # Voltage
            {"type": 10, "name": "Current Draw", "min": 0, "max": 100}       # Current
        ]
    },
    "Climate Control": {
        "description": "Advanced climate control system",
        "sensors": [
            {"type": 0, "name": "HVAC Temperature", "min": 15, "max": 30},   # Temperature
            {"type": 8, "name": "HVAC Humidity", "min": 30, "max": 70},      # Humidity
            {"type": 35, "name": "Comfort Index", "min": 0, "max": 100},     # Thermal Comfort
            {"type": 21, "name": "Air Pressure", "min": 980, "max": 1020},   # Barometric Pressure
            {"type": 12, "name": "Fan Speed", "min": 0, "max": 3000}         # Rotation Speed
        ]
    },
    "Water Monitor": {
        "description": "Water usage and leak detection",
        "sensors": [
            {"type": 30, "name": "Water Usage", "min": 0, "max": 1000},      # Water Consumption
            {"type": 2, "name": "Flow Rate", "min": 0, "max": 100},          # Flow Rate
            {"type": 27, "name": "Leak Sensor", "min": 0, "max": 1},         # Water Leak
            {"type": 1, "name": "Water Pressure", "min": 0, "max": 6}        # Pressure
        ]
    },
    "Weather Station": {
        "description": "Outdoor weather monitoring",
        "sensors": [
            {"type": 0, "name": "Outside Temperature", "min": -10, "max": 40},  # Temperature
            {"type": 8, "name": "Outside Humidity", "min": 0, "max": 100},      # Humidity
            {"type": 36, "name": "Rainfall", "min": 0, "max": 50},             # Rain
            {"type": 37, "name": "Wind Speed", "min": 0, "max": 100},          # Wind Speed
            {"type": 38, "name": "Wind Direction", "min": 0, "max": 360},      # Wind Direction
            {"type": 20, "name": "UV Level", "min": 0, "max": 11}              # UV Index
        ]
    }
}

# Simulation patterns for different times of day
TIME_PATTERNS = {
    "temperature": {
        "night": {"offset": -2, "variation": 0.5},
        "morning": {"offset": 0, "variation": 1},
        "day": {"offset": 2, "variation": 1.5},
        "evening": {"offset": 1, "variation": 1}
    },
    "occupancy": {
        "night": {"probability": 0.9, "variation": 0.1},
        "morning": {"probability": 0.7, "variation": 0.3},
        "day": {"probability": 0.3, "variation": 0.2},
        "evening": {"probability": 0.8, "variation": 0.2}
    },
    "energy": {
        "night": {"factor": 0.4, "variation": 0.2},
        "morning": {"factor": 1.2, "variation": 0.3},
        "day": {"factor": 0.8, "variation": 0.2},
        "evening": {"factor": 1.5, "variation": 0.4}
    }
}

# Scenario templates for different home states
SCENARIO_TEMPLATES = {
    "Home": {
        "description": "Normal occupied home state",
        "sensor_adjustments": {
            "temperature": {"offset": 0, "variation": 1},
            "motion": {"probability": 0.4},
            "energy": {"factor": 1}
        }
    },
    "Away": {
        "description": "Home unoccupied state",
        "sensor_adjustments": {
            "temperature": {"offset": 2, "variation": 0.5},
            "motion": {"probability": 0.01},
            "energy": {"factor": 0.3}
        }
    },
    "Night": {
        "description": "Nighttime home state",
        "sensor_adjustments": {
            "temperature": {"offset": -1, "variation": 0.5},
            "motion": {"probability": 0.1},
            "energy": {"factor": 0.4}
        }
    },
    "Vacation": {
        "description": "Extended away state",
        "sensor_adjustments": {
            "temperature": {"offset": 3, "variation": 0.3},
            "motion": {"probability": 0},
            "energy": {"factor": 0.2}
        }
    }
} 