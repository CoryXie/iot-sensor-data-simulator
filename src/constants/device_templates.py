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
        'rooms': ['bedroom', 'bathroom', 'kitchen'],
        'description': 'Morning activities across multiple rooms',
        'devices': [
            {
                'device': 'Environmental Monitor',
                'sensors': ['Temperature', 'Humidity'],
                'rooms': ['bedroom', 'bathroom']
            },
            {
                'device': 'Light Control',
                'sensors': ['Light Level', 'Color Temperature'],
                'rooms': ['bedroom', 'kitchen']
            }
        ]
    },
    'Day Mode': {
        'type': 'standard',
        'room_type': 'living_room',
        'description': 'Optimal daytime settings',
        'devices': [
            {
                'name': 'Environmental Monitor',
                'type': 'environmental',
                'sensors': [
                    {'name': 'Temperature', 'type': 'temperature', 'unit': '°C'}
                ]
            }
        ]
    },
    'Evening Mode': {
        'type': 'standard',
        'room_type': 'living_room',
        'description': 'Comfortable evening settings',
        'devices': [
            {
                'name': 'Light Control',
                'type': 'lighting',
                'sensors': [
                    {'name': 'Light Level', 'type': 'light', 'unit': 'lux'},
                    {'name': 'Color Temperature', 'type': 'color_temp', 'unit': 'K'}
                ]
            }
        ]
    },
    'Night Mode': {
        'type': 'night',
        'room_type': 'bedroom',
        'description': 'Settings for sleep and minimal activity',
        'devices': [
            {
                'name': 'Security System',
                'type': 'security',
                'sensors': [
                    {'name': 'Motion', 'type': 'motion'},
                    {'name': 'Door Status', 'type': 'contact'}
                ]
            }
        ]
    },
    'Away Mode': {
        'type': 'security',
        'rooms': ['living_room', 'garage', 'bedroom'],
        'description': 'Whole-home security scenario',
        'devices': [
            {
                'device': 'Security System',
                'sensors': ['Motion', 'Door Status'],
                'rooms': ['living_room', 'garage', 'bedroom']
            }
        ]
    },
    'Work From Home': {
        'type': 'work',
        'room_type': 'office',
        'description': 'Settings optimized for working from home',
        'devices': [
            {
                'name': 'Environmental Monitor',
                'type': 'environmental',
                'sensors': [
                    {'name': 'Temperature', 'type': 'temperature', 'unit': '°C'}
                ]
            }
        ]
    },
    'Entertainment Mode': {
        'type': 'entertainment',
        'room_type': 'living_room',
        'description': 'Settings for watching movies or entertainment',
        'devices': [
            {
                'name': 'Light Control',
                'type': 'lighting',
                'sensors': [
                    {'name': 'Light Level', 'type': 'light', 'unit': 'lux'}
                ]
            }
        ]
    },
    'Guest Mode': {
        'type': 'guest',
        'room_type': 'living_room',
        'description': 'Comfortable settings for guests',
        'devices': [
            {
                'name': 'Environmental Monitor',
                'type': 'environmental',
                'sensors': [
                    {'name': 'Temperature', 'type': 'temperature', 'unit': '°C'}
                ]
            }
        ]
    },
    'Emergency Mode': {
        'type': 'emergency',
        'room_type': 'living_room',
        'description': 'Highest security and safety settings',
        'devices': [
            {
                'name': 'Security System',
                'type': 'security',
                'sensors': [
                    {'name': 'Motion', 'type': 'motion'},
                    {'name': 'Door Status', 'type': 'contact'}
                ]
            }
        ]
    },
    'Eco Mode': {
        'type': 'efficiency',
        'room_type': 'living_room',
        'description': 'Maximum energy saving settings',
        'devices': [
            {
                'name': 'Environmental Monitor',
                'type': 'environmental',
                'sensors': [
                    {'name': 'Temperature', 'type': 'temperature', 'unit': '°C'}
                ]
            }
        ]
    },
    'Party Mode': {
        'type': 'comfort',
        'room_type': 'living_room',
        'description': 'Social gathering settings',
        'devices': [
            {
                'name': 'Light Control',
                'type': 'lighting',
                'sensors': [
                    {'name': 'Light Level', 'type': 'light', 'unit': 'lux'}
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