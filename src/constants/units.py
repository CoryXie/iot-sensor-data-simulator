# Description: Units for the sensor data
# Used to encode the unit of the sensor data in the database
UNITS = [
    {'id': 0, 'name': 'Temperature', 'symbol': '°C'},
    {'id': 1, 'name': 'Humidity', 'symbol': '%'},
    {'id': 2, 'name': 'Pressure', 'symbol': 'hPa'},
    {'id': 3, 'name': 'Air Quality', 'symbol': 'AQI'},
    {'id': 4, 'name': 'Light', 'symbol': 'lux'},
    {'id': 5, 'name': 'Status', 'symbol': ''},
    {'id': 6, 'name': 'Gas', 'symbol': 'ppm'},
    {'id': 7, 'name': 'Water', 'symbol': 'L'},
    {'id': 8, 'name': 'Motion', 'symbol': ''},
    {'id': 9, 'name': 'Energy', 'symbol': 'kWh'},
    {"id": 10, "name": "Current", "unit": "Ampere", "unit_abbreviation": "A"},
    {"id": 11, "name": "Power", "unit": "Watt", "unit_abbreviation": "W"},
    {"id": 12, "name": "Rotation Speed",
        "unit": "Revolutions per Minute", "unit_abbreviation": "rpm"},
    {"id": 13, "name": "Vibration", "unit": "G-force", "unit_abbreviation": "g"},
    {"id": 14, "name": "Brightness", "unit": "Lux", "unit_abbreviation": "lx"},
    # Environmental Sensors
    {"id": 15, "name": "Air Quality PM2.5", "unit": "Micrograms per Cubic Meter", "unit_abbreviation": "µg/m³"},
    {"id": 16, "name": "Air Quality PM10", "unit": "Micrograms per Cubic Meter", "unit_abbreviation": "µg/m³"},
    {"id": 17, "name": "CO2", "unit": "Parts per Million", "unit_abbreviation": "ppm"},
    {"id": 18, "name": "VOC", "unit": "Parts per Billion", "unit_abbreviation": "ppb"},
    {"id": 19, "name": "Noise Level", "unit": "Decibel", "unit_abbreviation": "dB"},
    {"id": 20, "name": "UV Index", "unit": "UV Index", "unit_abbreviation": "UVI"},
    {"id": 21, "name": "Barometric Pressure", "unit": "Hectopascal", "unit_abbreviation": "hPa"},
    # Security Sensors
    {"id": 22, "name": "Contact", "unit": "Boolean", "unit_abbreviation": "bool"},
    {"id": 23, "name": "Glass Break", "unit": "Boolean", "unit_abbreviation": "bool"},
    {"id": 24, "name": "Smoke", "unit": "Parts per Million", "unit_abbreviation": "ppm"},
    {"id": 25, "name": "Carbon Monoxide", "unit": "Parts per Million", "unit_abbreviation": "ppm"},
    {"id": 26, "name": "Water Leak", "unit": "Boolean", "unit_abbreviation": "bool"},
    # Energy Management
    {"id": 27, "name": "Energy Consumption", "unit": "Kilowatt Hour", "unit_abbreviation": "kWh"},
    {"id": 28, "name": "Gas Consumption", "unit": "Cubic Meter", "unit_abbreviation": "m³"},
    {"id": 29, "name": "Water Consumption", "unit": "Cubic Meter", "unit_abbreviation": "m³"},
    {"id": 30, "name": "Solar Output", "unit": "Kilowatt", "unit_abbreviation": "kW"},
    {"id": 31, "name": "Battery Level", "unit": "Percent", "unit_abbreviation": "%"},
    # Comfort Sensors
    {"id": 32, "name": "Occupancy", "unit": "Count", "unit_abbreviation": "n"},
    {"id": 33, "name": "Air Quality Index", "unit": "Index", "unit_abbreviation": "AQI"},
    {"id": 34, "name": "Thermal Comfort", "unit": "Index", "unit_abbreviation": "TCI"},
    {"id": 35, "name": "Rain", "unit": "Millimeters per Hour", "unit_abbreviation": "mm/h"},
    {"id": 36, "name": "Wind Speed", "unit": "Kilometers per Hour", "unit_abbreviation": "km/h"},
    {"id": 37, "name": "Wind Direction", "unit": "Degrees", "unit_abbreviation": "°"},
    # Additional Units
    {"id": 38, "name": "Percentage", "unit": "Percent", "unit_abbreviation": "%"},
    {"id": 39, "name": "Binary", "unit": "Boolean", "unit_abbreviation": "bool"},
    {"id": 40, "name": "Kelvin", "unit": "Kelvin", "unit_abbreviation": "K"},
    {"id": 41, "name": "PPM", "unit": "Parts per Million", "unit_abbreviation": "ppm"}
]
