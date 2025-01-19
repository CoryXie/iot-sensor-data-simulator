"""Device templates and room types for smart home simulation"""

ROOM_TYPES = [
    "Living Room",
    "Kitchen",
    "Bedroom",
    "Bathroom",
    "Office",
    "Garage"
]

DEVICE_TEMPLATES = {
    "Environmental Monitor": {
        "description": "Monitors and controls environmental conditions",
        "sensors": [
            {
                "name": "Temperature",
                "type": "Temperature",
                "min": 15,
                "max": 30,
                "unit": "Temperature",
                "variation": 0.5,
                "change_rate": 0.1,
                "interval": 5
            },
            {
                "name": "Humidity",
                "type": "Humidity",
                "min": 30,
                "max": 70,
                "unit": "Percentage",
                "variation": 2,
                "change_rate": 0.5,
                "interval": 10
            },
            {
                "name": "Air Quality",
                "type": "Air Quality",
                "min": 0,
                "max": 500,
                "unit": "PPM",
                "variation": 10,
                "change_rate": 2,
                "interval": 15
            }
        ]
    },
    "Security System": {
        "description": "Monitors home security",
        "sensors": [
            {
                "name": "Motion",
                "type": "Motion",
                "min": 0,
                "max": 100,
                "unit": "Percentage",
                "variation": 10,
                "change_rate": 50,
                "interval": 1
            },
            {
                "name": "Door Status",
                "type": "Status",
                "min": 0,
                "max": 1,
                "unit": "Binary",
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
        "description": "Controls lighting throughout the home",
        "sensors": [
            {
                "name": "Brightness",
                "type": "Light",
                "min": 0,
                "max": 100,
                "unit": "Percentage",
                "variation": 5,
                "change_rate": 10,
                "interval": 1
            },
            {
                "name": "Color Temperature",
                "type": "Temperature",
                "min": 2700,
                "max": 6500,
                "unit": "Kelvin",
                "variation": 100,
                "change_rate": 50,
                "interval": 2
            }
        ]
    },
    "Safety Monitor": {
        "description": "Monitors safety conditions",
        "sensors": [
            {
                "name": "Smoke Level",
                "type": "Smoke",
                "min": 0,
                "max": 100,
                "unit": "PPM",
                "variation": 1,
                "change_rate": 5,
                "interval": 1
            },
            {
                "name": "CO Level",
                "type": "Gas",
                "min": 0,
                "max": 100,
                "unit": "PPM",
                "variation": 1,
                "change_rate": 2,
                "interval": 1
            },
            {
                "name": "Water Leak",
                "type": "Water",
                "min": 0,
                "max": 1,
                "unit": "Binary",
                "variation": 1,
                "change_rate": 1,
                "interval": 1
            }
        ]
    }
}

SCENARIO_TEMPLATES = {
    "Morning Routine": {
        "description": "Early morning activities with gradual light and temperature changes",
        "devices": ["Environmental Monitor", "Light Control", "Security System"],
        "transitions": ["Day Mode", "Away Mode", "Work From Home"]
    },
    "Day Mode": {
        "description": "Optimal settings for daytime activities with balanced temperature and lighting",
        "devices": ["Environmental Monitor", "Light Control", "Security System", "Safety Monitor"],
        "transitions": ["Evening Mode", "Away Mode", "Work From Home"]
    },
    "Evening Mode": {
        "description": "Comfortable evening settings with warm lighting and relaxed temperature",
        "devices": ["Environmental Monitor", "Light Control", "Security System", "Safety Monitor"],
        "transitions": ["Night Mode", "Entertainment Mode", "Guest Mode"]
    },
    "Night Mode": {
        "description": "Quiet hours with minimal lighting and energy-saving temperature",
        "devices": ["Environmental Monitor", "Light Control", "Security System"],
        "transitions": ["Morning Routine", "Emergency Mode"]
    },
    "Away Mode": {
        "description": "Energy-saving mode with enhanced security when no one is home",
        "devices": ["Environmental Monitor", "Security System", "Safety Monitor"],
        "transitions": ["Morning Routine", "Day Mode", "Evening Mode", "Emergency Mode"]
    },
    "Work From Home": {
        "description": "Optimal settings for productivity with proper lighting and temperature",
        "devices": ["Environmental Monitor", "Light Control", "Security System"],
        "transitions": ["Evening Mode", "Day Mode"]
    },
    "Entertainment Mode": {
        "description": "Perfect ambiance for movies or gatherings with mood lighting",
        "devices": ["Environmental Monitor", "Light Control", "Security System"],
        "transitions": ["Evening Mode", "Night Mode"]
    },
    "Guest Mode": {
        "description": "Welcoming settings for visitors with comfortable temperature and lighting",
        "devices": ["Environmental Monitor", "Light Control", "Security System", "Safety Monitor"],
        "transitions": ["Evening Mode", "Night Mode"]
    },
    "Vacation Mode": {
        "description": "Extended away settings with randomized lighting and strict security",
        "devices": ["Environmental Monitor", "Light Control", "Security System", "Safety Monitor"],
        "transitions": ["Morning Routine", "Away Mode", "Emergency Mode"]
    },
    "Emergency Mode": {
        "description": "Maximum security and safety settings with emergency lighting",
        "devices": ["Environmental Monitor", "Light Control", "Security System", "Safety Monitor"],
        "transitions": ["Morning Routine", "Day Mode", "Away Mode"]
    },
    "Energy Saving": {
        "description": "Minimum energy consumption while maintaining basic comfort",
        "devices": ["Environmental Monitor", "Light Control", "Security System"],
        "transitions": ["Morning Routine", "Day Mode", "Away Mode"]
    },
    "Party Mode": {
        "description": "Dynamic lighting and comfortable temperature for social gatherings",
        "devices": ["Environmental Monitor", "Light Control", "Security System"],
        "transitions": ["Evening Mode", "Night Mode", "Entertainment Mode"]
    }
} 