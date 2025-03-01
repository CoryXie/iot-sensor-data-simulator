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
        'devices': ['Environmental Monitor', 'Light Control', 'Security System'],
        'base_temperature': 22.0,
        'base_humidity': 45.0,
        'base_light': 400.0
    },
    'Kitchen': {
        'room_type': 'kitchen',
        'description': 'Area for cooking and food preparation',
        'devices': ['Environmental Monitor', 'Light Control', 'Safety Monitor'],
        'base_temperature': 20.0,
        'base_humidity': 50.0,
        'base_light': 600.0
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
                "min_value": 15,
                "max_value": 35,
                "variation_range": 2.0,
                "change_rate": 0.5,
                "interval": 5
            },
            {
                "name": "Humidity",
                "type": "humidity",
                "unit": "%",
                "min_value": 20,
                "max_value": 90,
                "variation_range": 5.0,
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
                "min_value": 0,
                "max_value": 1,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 1
            },
            {
                "name": "Door Status",
                "type": "contact_sensor",
                "min_value": 0,
                "max_value": 1,
                "unit": "binary",
                "variation_range": 1,
                "change_rate": 1,
                "interval": 1
            },
            {
                "name": "Window Status",
                "type": "Status",
                "min_value": 0,
                "max_value": 1,
                "unit": "Binary",
                "variation_range": 1,
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
                "name": "Light Level",
                "type": "light",
                "unit": "lux",
                "min_value": 0,
                "max_value": 1000,
                "variation_range": 100,
                "change_rate": 2.0,
                "interval": 2
            },
            {
                "name": "Color Temperature",
                "type": "color_temp",
                "min_value": 2700,
                "max_value": 6500,
                "unit": "kelvin",
                "variation_range": 100,
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
                "name": "Smoke",
                "type": "smoke",
                "unit": "ppm",
                "min_value": 0,
                "max_value": 100,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 5
            },
            {
                "name": "CO Level",
                "type": "co",
                "min_value": 0,
                "max_value": 1000,
                "unit": "ppm",
                "variation_range": 10,
                "change_rate": 5,
                "interval": 5
            }
        ]
    },
    "Whole Home AC": {
        "type": "hvac_system",
        "description": "Central air conditioning system",
        "icon": "mdi-air-conditioner",
        "sensors": [
            {
                "name": "Temperature",
                "type": "temperature", 
                "unit": "°C",
                "min_value": 15,
                "max_value": 35,
                "variation_range": 0.5,
                "change_rate": 0.2,
                "interval": 2
            },
            {
                "name": "Set Temperature",
                "type": "set_temperature",
                "unit": "°C",
                "min_value": 16,
                "max_value": 30,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 5
            },
            {
                "name": "Mode",
                "type": "mode",
                "unit": "mode",
                "min_value": 0,
                "max_value": 4, 
                "variation_range": 0,
                "change_rate": 0,
                "interval": 5
            },
            {
                "name": "Fan Speed",
                "type": "fan_speed",
                "unit": "level",
                "min_value": 1,
                "max_value": 5,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 5
            },
            {
                "name": "Power",
                "type": "power",
                "unit": "binary",
                "min_value": 0,
                "max_value": 1,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 1
            }
        ]
    },
    "Smart Thermostat": {
        "type": "thermostat",
        "description": "Smart room temperature control",
        "icon": "mdi-thermostat",
        "sensors": [
            {
                "name": "Temperature",
                "type": "temperature",
                "unit": "°C",
                "min_value": 0,
                "max_value": 40,
                "variation_range": 1.0,
                "change_rate": 0.5,
                "interval": 5
            },
            {
                "name": "Set Temperature",
                "type": "set_temperature",
                "unit": "°C",
                "min_value": 16,
                "max_value": 30,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 5
            },
            {
                "name": "Humidity",
                "type": "humidity",
                "unit": "%",
                "min_value": 0,
                "max_value": 100,
                "variation_range": 5.0,
                "change_rate": 1.0,
                "interval": 10
            },
            {
                "name": "Mode",
                "type": "mode",
                "unit": "mode",
                "min_value": 0,
                "max_value": 3,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 5
            },
            {
                "name": "Power",
                "type": "power",
                "unit": "binary",
                "min_value": 0,
                "max_value": 1,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 1
            }
        ]
    },
    "Smart Blinds": {
        "type": "blinds",
        "description": "Automated window blinds",
        "icon": "mdi-blinds",
        "sensors": [
            {
                "name": "Position",
                "type": "position",
                "unit": "%",
                "min_value": 0,
                "max_value": 100,
                "variation_range": 0,
                "change_rate": 5,
                "interval": 2
            },
            {
                "name": "Light Level",
                "type": "light",
                "unit": "lux",
                "min_value": 0,
                "max_value": 1000,
                "variation_range": 50,
                "change_rate": 10,
                "interval": 5
            },
            {
                "name": "Mode",
                "type": "mode",
                "unit": "mode",
                "min_value": 0,
                "max_value": 2,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 5
            }
        ]
    },
    "Smart Irrigation": {
        "type": "irrigation",
        "description": "Automated garden watering system",
        "icon": "mdi-water-pump",
        "sensors": [
            {
                "name": "Soil Moisture",
                "type": "moisture",
                "unit": "%",
                "min_value": 0,
                "max_value": 100,
                "variation_range": 2.0,
                "change_rate": 0.5,
                "interval": 30
            },
            {
                "name": "Water Flow",
                "type": "flow",
                "unit": "L/min",
                "min_value": 0,
                "max_value": 10,
                "variation_range": 0.2,
                "change_rate": 0.1,
                "interval": 5
            },
            {
                "name": "Schedule",
                "type": "schedule",
                "unit": "status",
                "min_value": 0,
                "max_value": 1,
                "variation_range": 0,
                "change_rate": 0,
                "interval": 60
            }
        ]
    }
}

SCENARIO_TEMPLATES = {
    'Morning Routine': {
        'type': 'routine',
        'description': 'Morning activities across multiple rooms',
        'containers': [
            {
                'room_type': 'bedroom',
                'devices': [
                    {'device_type': 'Environmental Monitor'},
                    {'device_type': 'Light Control'}
                ]
            },
            {
                'room_type': 'bathroom',
                'devices': [
                    {'device_type': 'Environmental Monitor'}
                ]
            },
            {
                'room_type': 'kitchen',
                'devices': [
                    {'device_type': 'Light Control'}
                ]
            }
        ]
    },
    'Day Mode': {
        'type': 'standard',
        'description': 'Optimal daytime settings',
        'containers': [
            {
                'room_type': 'living_room',
                'devices': [
                    {'device_type': 'Environmental Monitor'}
                ]
            }
        ]
    },
    'Evening Mode': {
        'type': 'standard',
        'description': 'Comfortable evening settings',
        'containers': [
            {
                'room_type': 'living_room',
                'devices': [
                    {'device_type': 'Light Control'}
                ]
            }
        ]
    },
    'Night Mode': {
        'type': 'night',
        'description': 'Settings for sleep and minimal activity',
        'containers': [
            {
                'room_type': 'bedroom',
                'devices': [
                    {'device_type': 'Security System'}
                ]
            }
        ]
    },
    'Away Mode': {
        'type': 'security',
        'description': 'Whole-home security scenario',
        'containers': [
            {
                'room_type': 'living_room',
                'devices': [
                    {'device_type': 'Security System'}
                ]
            },
            {
                'room_type': 'garage',
                'devices': [
                    {'device_type': 'Security System'}
                ]
            },
            {
                'room_type': 'bedroom',
                'devices': [
                    {'device_type': 'Security System'}
                ]
            }
        ]
    },
    'Work From Home': {
        'type': 'work',
        'description': 'Settings optimized for working from home',
        'containers': [
            {
                'room_type': 'office',
                'devices': [
                    {'device_type': 'Environmental Monitor'}
                ]
            }
        ]
    },
    'Entertainment Mode': {
        'type': 'entertainment',
        'description': 'Settings for watching movies or entertainment',
        'containers': [
            {
                'room_type': 'living_room',
                'devices': [
                    {'device_type': 'Light Control'}
                ]
            }
        ]
    },
    'Guest Mode': {
        'type': 'guest',
        'description': 'Comfortable settings for guests',
        'containers': [
            {
                'room_type': 'living_room',
                'devices': [
                    {'device_type': 'Environmental Monitor'}
                ]
            }
        ]
    },
    'Emergency Mode': {
        'type': 'emergency',
        'description': 'Highest security and safety settings',
        'containers': [
            {
                'room_type': 'living_room',
                'devices': [
                    {'device_type': 'Security System'}
                ]
            }
        ]
    },
    'Eco Mode': {
        'type': 'efficiency',
        'description': 'Maximum energy saving settings',
        'containers': [
            {
                'room_type': 'living_room',
                'devices': [
                    {'device_type': 'Environmental Monitor'}
                ]
            }
        ]
    },
    'Party Mode': {
        'type': 'comfort',
        'description': 'Social gathering settings',
        'containers': [
            {
                'room_type': 'living_room',
                'devices': [
                    {'device_type': 'Light Control'}
                ]
            }
        ]
    }
}

DEVICE_ICONS = {
    'thermostat': 'thermostat',
    'light': 'lightbulb',
    'security_camera': 'videocam',
    'motion_sensor': 'sensors',
    'smart_lock': 'lock',
    'humidity_sensor': 'water_drop',
    'default': 'device_unknown'
}

STATUS_COLORS = {
    'active': '#4CAF50',  # Green
    'inactive': '#9E9E9E', # Grey
    'alert': '#F44336'     # Red
}