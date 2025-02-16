"""Device templates and room types for smart home simulation"""

ROOM_TYPES = [
    'Living Room',
    'Kitchen',
    'Bedroom',
    'Bathroom',
    'Office',
    'Garage'
]

ROOM_TEMPLATES = {
    'Living Room': {
        'room_type': 'living_room',
        'description': 'General living and relaxation area',
        'devices': ['Environmental Monitor', 'Light Control', 'Security System']
    },
    'Kitchen': {
        'room_type': 'kitchen',
        'description': 'Area for cooking and food preparation',
        'devices': ['Environmental Monitor', 'Light Control', 'Safety Monitor']
    },
    'Bedroom': {
        'room_type': 'bedroom',
        'description': 'Private sleeping quarters',
        'devices': ['Environmental Monitor', 'Light Control', 'Security System']
    },
    'Bathroom': {
        'room_type': 'bathroom',
        'description': 'Hygiene and sanitation facilities',
        'devices': ['Environmental Monitor', 'Light Control', 'Safety Monitor']
    },
    'Office': {
        'room_type': 'office',
        'description': 'Workspace for home office activities',
        'devices': ['Environmental Monitor', 'Light Control', 'Security System']
    },
    'Garage': {
        'room_type': 'garage',
        'description': 'Vehicle storage and workshop area',
        'devices': ['Environmental Monitor', 'Light Control', 'Security System', 'Safety Monitor']
    }
}

DEVICE_TEMPLATES = {
    "Environmental Monitor": {
        "type": "sensor_hub",
        "description": "Monitors environmental conditions",
        "icon": "mdi-thermometer",
        "sensors": [
            {
                "name": "Temperature",
                "type": "temperature",
                "unit": "°C",
                "min": 15,
                "max": 35,
                "variation": 2.0,
                "change_rate": 0.5,
                "interval": 5
            },
            {
                "name": "Humidity",
                "type": "humidity",
                "unit": "%",
                "min": 20,
                "max": 90,
                "variation": 5.0,
                "change_rate": 1.0,
                "interval": 5
            }
        ]
    },
    "Security System": {
        "type": "security_system",
        "description": "Monitors home security",
        "icon": "mdi-shield-home",
        "sensors": [
            {
                "name": "Motion",
                "type": "motion",
                "min": 0,
                "max": 100,
                "unit": "percentage",
                "variation": 10,
                "change_rate": 50,
                "interval": 1
            },
            {
                "name": "Door Status",
                "type": "contact_sensor",
                "min": 0,
                "max": 1,
                "unit": "binary",
                "variation": 1,
                "change_rate": 1,
                "interval": 1
            },
            {
                "name": "Window Status",
                "type": "Status",
                "min": 0,
                "max": 1,
                "unit": "Binary",
                "variation": 1,
                "change_rate": 1,
                "interval": 1
            }
        ]
    },
    "Light Control": {
        "type": "lighting",
        "description": "Smart lighting system",
        "icon": "mdi-lightbulb",
        "sensors": [
            {
                "name": "Brightness",
                "type": "brightness",
                "unit": "%",
                "min": 0,
                "max": 100,
                "variation": 10.0,
                "change_rate": 5.0,
                "interval": 2
            },
            {
                "name": "Color Temperature",
                "type": "color_temp",
                "min": 2700,
                "max": 6500,
                "unit": "kelvin",
                "variation": 100,
                "change_rate": 50,
                "interval": 2
            }
        ]
    },
    "Safety Monitor": {
        "type": "safety_system",
        "description": "Monitors safety conditions",
        "icon": "mdi-alarm-light",
        "sensors": [
            {
                "name": "Smoke Level",
                "type": "smoke",
                "min": 0,
                "max": 100,
                "unit": "percentage",
                "variation": 5,
                "change_rate": 2,
                "interval": 5
            },
            {
                "name": "CO Level",
                "type": "co",
                "min": 0,
                "max": 1000,
                "unit": "ppm",
                "variation": 10,
                "change_rate": 5,
                "interval": 5
            }
        ]
    }
}

SCENARIO_TEMPLATES = {
    "Morning Routine": {
        "description": "Early morning activities with gradual light and temperature changes",
        "type": "routine",
        "devices": ["Environmental Monitor", "Light Control", "Security System"],
        "rooms": ["living_room", "bedroom", "kitchen"],
        "transitions": ["Day Mode", "Away Mode", "Work From Home"],
        "sensor_adjustments": {
            "temperature": {"offset": 2, "variation": 1},
            "motion": {"probability": 0.3},
            "energy": {"factor": 0.8}
        },
        "is_active": False
    },
    "Day Mode": {
        "description": "Optimal settings for daytime activities",
        "type": "standard",
        "devices": ["Environmental Monitor", "Light Control", "Security System", "Safety Monitor"],
        "rooms": ["living_room", "kitchen", "office"],
        "transitions": ["Evening Mode", "Away Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": 0, "variation": 1.5},
            "motion": {"probability": 0.1},
            "energy": {"factor": 1.0}
        },
        "is_active": False
    },
    "Evening Mode": {
        "description": "Comfortable evening settings",
        "type": "standard",
        "devices": ["Environmental Monitor", "Light Control", "Security System", "Safety Monitor"],
        "transitions": ["Night Mode", "Entertainment Mode", "Guest Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": -2, "variation": 1},
            "motion": {"probability": 0.2},
            "energy": {"factor": 0.9}
        },
        "is_active": False
    },
    "Night Mode": {
        "description": "Settings for sleep and minimal activity",
        "type": "night",
        "devices": ["Environmental Monitor", "Security System"],
        "rooms": ["bedroom"],
        "transitions": ["Morning Routine", "Away Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": -4, "variation": 0.5},
            "motion": {"probability": 0.01},
            "energy": {"factor": 0.5}
        },
        "is_active": False
    },
    "Away Mode": {
        "description": "Energy-saving and security settings when no one is home",
        "type": "security",
        "devices": ["Environmental Monitor", "Security System", "Safety Monitor"],
        "rooms": ["living_room", "bedroom", "kitchen", "office", "garage"],
        "transitions": ["Home", "Morning Routine", "Day Mode", "Evening Mode", "Night Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": -5, "variation": 2},
            "motion": {"probability": 0.0},
            "energy": {"factor": 0.3}
        },
        "is_active": False
    },
    "Work From Home": {
        "description": "Settings optimized for working from home",
        "type": "work",
        "devices": ["Environmental Monitor", "Light Control", "Security System", "Safety Monitor"],
        "rooms": ["office", "living_room"],
        "transitions": ["Day Mode", "Evening Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": 1, "variation": 1},
            "motion": {"probability": 0.2},
            "energy": {"factor": 1.1}
        },
        "is_active": False
    },
    "Entertainment Mode": {
        "description": "Settings for watching movies or entertainment",
        "type": "entertainment",
        "devices": ["Light Control", "Environmental Monitor"],
        "rooms": ["living_room"],
        "transitions": ["Evening Mode", "Night Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": -1, "variation": 0.5},
            "motion": {"probability": 0.15},
            "energy": {"factor": 0.7}
        },
        "is_active": False
    },
    "Guest Mode": {
        "description": "Comfortable settings for guests",
        "type": "guest",
        "devices": ["Environmental Monitor", "Light Control"],
        "rooms": ["living_room", "bedroom", "guest_room"],
        "transitions": ["Day Mode", "Evening Mode", "Night Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": 1, "variation": 1.5},
            "motion": {"probability": 0.4},
            "energy": {"factor": 1.2}
        },
        "is_active": False
    },
    "Emergency Mode": {
        "description": "Highest security and safety settings",
        "type": "emergency",
        "devices": ["Security System", "Safety Monitor", "Environmental Monitor"],
        "rooms": ["living_room", "bedroom", "kitchen", "office", "garage"],
        "transitions": [],
        "sensor_adjustments": {
            "temperature": {"offset": -3, "variation": 3},
            "motion": {"probability": 0.6},
            "energy": {"factor": 1.0}
        },
        "is_active": False
    },
    "Eco Mode": {
        "description": "Maximum energy saving settings",
        "type": "efficiency",
        "devices": ["Environmental Monitor", "Light Control"],
        "rooms": ["living_room", "bedroom", "kitchen"],
        "transitions": ["Day Mode", "Away Mode", "Night Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": -4, "variation": 1},
            "motion": {"probability": 0.05},
            "energy": {"factor": 0.2}
        },
        "is_active": False
    },
    "Party Mode": {
        "description": "Social gathering settings",
        "type": "comfort",
        "devices": ["Environmental Monitor", "Light Control", "Security System"],
        "rooms": ["living_room", "kitchen"],
        "transitions": ["Evening Mode", "Night Mode"],
        "sensor_adjustments": {
            "temperature": {"offset": 2, "variation": 2},
            "motion": {"probability": 0.7},
            "energy": {"factor": 1.5}
        },
        "is_active": False
    }
}