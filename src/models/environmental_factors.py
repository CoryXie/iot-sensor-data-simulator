"""Environmental factors affecting sensor data simulation"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

class WeatherCondition(Enum):
    SUNNY = "sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    OVERCAST = "overcast"
    LIGHT_RAIN = "light_rain"
    RAINY = "rainy"
    HEAVY_RAIN = "heavy_rain"
    STORMY = "stormy"
    LIGHT_SNOW = "light_snow"
    SNOWY = "snowy"
    HEAVY_SNOW = "heavy_snow"
    FOGGY = "foggy"
    WINDY = "windy"

class TimeOfDay(Enum):
    NIGHT = "night"  # 00:00-06:00
    MORNING = "morning"  # 06:00-12:00
    AFTERNOON = "afternoon"  # 12:00-18:00
    EVENING = "evening"  # 18:00-24:00

@dataclass
class Location:
    region: str
    latitude: float
    longitude: float
    timezone: str
    
    @property
    def zone_info(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

class SimulationTime:
    """Class to handle simulation time"""
    def __init__(self, start_time: datetime = None, custom_time: time = None, time_factor: float = 1.0):
        self.start_time = start_time or datetime.now()
        self.time_factor = time_factor
        self.current_time = self.start_time
        self.last_update = datetime.now()
        self.custom_time = custom_time
        
        # Set effective time based on custom time if provided
        if custom_time:
            current_date = self.current_time.date()
            self.effective_time = datetime.combine(current_date, custom_time)
        else:
            self.effective_time = self.current_time

    def update(self):
        """Update simulation time based on time factor"""
        now = datetime.now()
        elapsed = (now - self.last_update).total_seconds()
        simulated_elapsed = elapsed * self.time_factor
        self.current_time = self.current_time + timedelta(seconds=simulated_elapsed)
        
        # Update effective time
        if self.custom_time:
            current_date = self.current_time.date()
            self.effective_time = datetime.combine(current_date, self.custom_time)
        else:
            self.effective_time = self.current_time
            
        self.last_update = now

    def get_current_time(self) -> datetime:
        """Get current simulation time"""
        self.update()
        return self.effective_time

    def set_time_factor(self, factor: float):
        """Set simulation time factor"""
        self.time_factor = max(0.1, min(factor, 10.0))  # Limit between 0.1x and 10x

    def reset(self, start_time: datetime = None):
        """Reset simulation time"""
        self.start_time = start_time or datetime.now()
        self.current_time = self.start_time
        if self.custom_time:
            current_date = self.current_time.date()
            self.effective_time = datetime.combine(current_date, self.custom_time)
        else:
            self.effective_time = self.current_time
        self.last_update = datetime.now()

@dataclass
class WeatherImpactFactors:
    """Impact factors of weather on sensor readings"""
    temperature_modifier: float  # Celsius modifier
    humidity_modifier: float    # Percentage points modifier
    light_level_modifier: float # Percentage points modifier
    air_quality_modifier: float # AQI points modifier
    noise_level_modifier: float # Decibel modifier
    wind_chill_modifier: float  # Wind chill effect
    heat_index_modifier: float  # Heat index effect
    pressure_modifier: float    # Pressure modifier
    
    @classmethod
    def get_impact_factors(cls, condition: WeatherCondition, temp: float = 20.0, humidity: float = 50.0) -> 'WeatherImpactFactors':
        """Get impact factors considering temperature and humidity"""
        base_factors = {
            WeatherCondition.SUNNY: cls(3.0, -10.0, 30.0, -8.0, 0.0, 0.0, 1.2, -2.0),
            WeatherCondition.PARTLY_CLOUDY: cls(1.0, -5.0, 15.0, -4.0, 0.0, 0.5, 1.0, -1.0),
            WeatherCondition.CLOUDY: cls(-0.5, 5.0, -20.0, 2.0, 0.0, 0.8, 0.9, 0.0),
            WeatherCondition.OVERCAST: cls(-1.5, 10.0, -30.0, 5.0, 0.0, 1.0, 0.8, 1.0),
            WeatherCondition.LIGHT_RAIN: cls(-2.0, 20.0, -40.0, -5.0, 5.0, 1.2, 0.7, 2.0),
            WeatherCondition.RAINY: cls(-3.0, 30.0, -50.0, -10.0, 10.0, 1.5, 0.6, 3.0),
            WeatherCondition.HEAVY_RAIN: cls(-4.0, 40.0, -60.0, -15.0, 15.0, 1.8, 0.5, 4.0),
            WeatherCondition.STORMY: cls(-5.0, 50.0, -70.0, -20.0, 25.0, 2.0, 0.4, 5.0),
            WeatherCondition.LIGHT_SNOW: cls(-6.0, -5.0, -30.0, 5.0, -5.0, 2.2, 0.3, 3.0),
            WeatherCondition.SNOWY: cls(-8.0, -10.0, -40.0, 8.0, -8.0, 2.5, 0.2, 4.0),
            WeatherCondition.HEAVY_SNOW: cls(-10.0, -15.0, -50.0, 10.0, -10.0, 3.0, 0.1, 5.0),
            WeatherCondition.FOGGY: cls(-1.0, 25.0, -45.0, 15.0, -5.0, 1.3, 0.7, 1.0),
            WeatherCondition.WINDY: cls(-2.0, -15.0, -10.0, -12.0, 20.0, 2.0, 0.8, -2.0)
        }
        
        factors = base_factors.get(condition, cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        
        # Adjust for extreme temperatures
        if temp > 30:  # Hot weather
            factors.temperature_modifier *= 1.2
            factors.humidity_modifier *= 1.3
        elif temp < 0:  # Cold weather
            factors.temperature_modifier *= 0.8
            factors.humidity_modifier *= 0.7
            
        # Adjust for humidity
        if humidity > 80:  # High humidity
            factors.heat_index_modifier *= 1.3
        elif humidity < 30:  # Low humidity
            factors.heat_index_modifier *= 0.7
            
        return factors

@dataclass
class EnvironmentalState:
    """Class to hold environmental state data"""
    location: Location = None
    weather_condition: WeatherCondition = None
    simulation_time: SimulationTime = None
    temperature_celsius: float = 20.0  # Default temperature
    humidity_percent: float = 50.0     # Default humidity
    light_level_percent: float = 50.0  # Default light level

    def __post_init__(self):
        """Initialize default values"""
        if self.location is None:
            self.location = Location(
                region="New York",
                latitude=40.7128,
                longitude=-74.0060,
                timezone="America/New_York"
            )
        if self.weather_condition is None:
            self.weather_condition = WeatherCondition.SUNNY  # Use enum value directly
        if self.simulation_time is None:
            self.simulation_time = SimulationTime()

    def update_weather(self, weather: WeatherCondition, temperature: float = None, humidity: float = None):
        """Update weather condition and related metrics"""
        self.weather_condition = weather
        if temperature is not None:
            self.temperature_celsius = temperature
        if humidity is not None:
            self.humidity_percent = humidity
        # Update light level based on weather and time
        self.light_level_percent = self._calculate_light_level(weather, self.get_current_time())

    def update_location(self, location: Location):
        """Update location"""
        self.location = location

    def update_time(self, time_factor: float = None):
        """Update simulation time"""
        if time_factor is not None:
            self.simulation_time.set_time_factor(time_factor)
        self.simulation_time.update()

    def get_current_time(self) -> datetime:
        """Get current simulation time"""
        return self.simulation_time.get_current_time()

    @classmethod
    def get_time_of_day(cls, current_time: datetime) -> TimeOfDay:
        hour = current_time.hour
        if 0 <= hour < 6:
            return TimeOfDay.NIGHT
        elif 6 <= hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= hour < 18:
            return TimeOfDay.AFTERNOON
        else:
            return TimeOfDay.EVENING

    @classmethod
    def create_default(cls, weather: WeatherCondition, current_time: datetime, location: Location) -> 'EnvironmentalState':
        """Create environmental state with sensible defaults based on weather and time"""
        # Convert time to location's timezone
        local_time = current_time.astimezone(location.zone_info)
        time_of_day = cls.get_time_of_day(local_time)
        
        # Base temperature ranges for different times of day
        temp_ranges = {
            TimeOfDay.NIGHT: (15, 20),
            TimeOfDay.MORNING: (18, 23),
            TimeOfDay.AFTERNOON: (22, 28),
            TimeOfDay.EVENING: (20, 25)
        }
        
        # Calculate base temperature
        base_temp_range = temp_ranges[time_of_day]
        base_temp = (base_temp_range[0] + base_temp_range[1]) / 2
        
        # Get weather modifiers
        weather_modifiers = WeatherImpactFactors.get_impact_factors(
            weather,
            base_temp,
            50  # Default humidity for initial state
        )
        
        # Apply weather modifiers
        temp = base_temp + weather_modifiers.temperature_modifier
        humidity = 50 + weather_modifiers.humidity_modifier  # Base humidity of 50%
        
        simulation_time = SimulationTime(local_time)
        
        # Calculate light level
        light_level = cls._calculate_light_level(weather, local_time)
        
        return cls(
            weather_condition=weather,
            location=location,
            simulation_time=simulation_time,
            temperature_celsius=temp,
            humidity_percent=humidity,
            light_level_percent=light_level
        )

    @classmethod
    def from_weather_data(cls, weather_data: dict, location: Location, simulation_time: SimulationTime) -> 'EnvironmentalState':
        """Create environmental state from weather API data"""
        # Handle weather condition that could be string or WeatherCondition enum
        weather_condition = weather_data.get('weather_condition', WeatherCondition.SUNNY)
        if isinstance(weather_condition, str):
            try:
                weather_condition = WeatherCondition[weather_condition.upper()]
            except KeyError:
                weather_condition = WeatherCondition.SUNNY  # Default to sunny if invalid
        elif not isinstance(weather_condition, WeatherCondition):
            weather_condition = WeatherCondition.SUNNY  # Default if not string or enum
        
        # Extract temperature and humidity from weather data
        temperature = weather_data.get('temperature', 20.0)  # Default to 20°C
        humidity = weather_data.get('humidity', 50.0)       # Default to 50%
        
        # Calculate light level based on weather and time
        light_level = cls._calculate_light_level(weather_condition, simulation_time.get_current_time())
            
        return cls(
            weather_condition=weather_condition,
            location=location,
            simulation_time=simulation_time,
            temperature_celsius=temperature,
            humidity_percent=humidity,
            light_level_percent=light_level
        )
        
    @classmethod
    def _calculate_light_level(cls, weather: WeatherCondition, time: datetime) -> float:
        """Calculate light level based on weather and time"""
        base_light = {
            TimeOfDay.NIGHT: 5,
            TimeOfDay.MORNING: 70,
            TimeOfDay.AFTERNOON: 100,
            TimeOfDay.EVENING: 40
        }[cls.get_time_of_day(time)]
        
        weather_modifier = WeatherImpactFactors.get_impact_factors(
            weather,
            time.hour * 2 if 6 <= time.hour <= 18 else 15,  # Rough temperature estimate based on time
            50  # Default humidity
        ).light_level_modifier
        return min(100, base_light + weather_modifier)

def get_sensor_value_modifier(env_state: EnvironmentalState, sensor_type: str) -> float:
    """Get modifier for sensor values based on environmental conditions"""
    current_time = env_state.get_current_time()
    time_of_day = EnvironmentalState.get_time_of_day(current_time)
    
    modifiers = {
        "temperature": {
            WeatherCondition.SUNNY: lambda: 1.2,
            WeatherCondition.PARTLY_CLOUDY: lambda: 1.0,
            WeatherCondition.CLOUDY: lambda: 1.0,
            WeatherCondition.OVERCAST: lambda: 0.9,
            WeatherCondition.LIGHT_RAIN: lambda: 0.9,
            WeatherCondition.RAINY: lambda: 0.8,
            WeatherCondition.HEAVY_RAIN: lambda: 0.7,
            WeatherCondition.STORMY: lambda: 0.6,
            WeatherCondition.LIGHT_SNOW: lambda: 0.6,
            WeatherCondition.SNOWY: lambda: 0.5,
            WeatherCondition.HEAVY_SNOW: lambda: 0.4,
            WeatherCondition.FOGGY: lambda: 0.9,
            WeatherCondition.WINDY: lambda: 0.9
        },
        "humidity": {
            WeatherCondition.SUNNY: lambda: 0.8,
            WeatherCondition.PARTLY_CLOUDY: lambda: 1.0,
            WeatherCondition.CLOUDY: lambda: 1.0,
            WeatherCondition.OVERCAST: lambda: 1.1,
            WeatherCondition.LIGHT_RAIN: lambda: 1.3,
            WeatherCondition.RAINY: lambda: 1.4,
            WeatherCondition.HEAVY_RAIN: lambda: 1.5,
            WeatherCondition.STORMY: lambda: 1.6,
            WeatherCondition.LIGHT_SNOW: lambda: 1.1,
            WeatherCondition.SNOWY: lambda: 1.2,
            WeatherCondition.HEAVY_SNOW: lambda: 1.3,
            WeatherCondition.FOGGY: lambda: 1.2,
            WeatherCondition.WINDY: lambda: 0.9
        },
        "light": {
            WeatherCondition.SUNNY: lambda: 1.5,
            WeatherCondition.PARTLY_CLOUDY: lambda: 0.7,
            WeatherCondition.CLOUDY: lambda: 0.7,
            WeatherCondition.OVERCAST: lambda: 0.5,
            WeatherCondition.LIGHT_RAIN: lambda: 0.5,
            WeatherCondition.RAINY: lambda: 0.3,
            WeatherCondition.HEAVY_RAIN: lambda: 0.2,
            WeatherCondition.STORMY: lambda: 0.1,
            WeatherCondition.LIGHT_SNOW: lambda: 1.0,
            WeatherCondition.SNOWY: lambda: 0.9,
            WeatherCondition.HEAVY_SNOW: lambda: 0.8,
            WeatherCondition.FOGGY: lambda: 0.6,
            WeatherCondition.WINDY: lambda: 0.9
        },
        "motion": {
            TimeOfDay.NIGHT: lambda: 0.2,
            TimeOfDay.MORNING: lambda: 1.0,
            TimeOfDay.AFTERNOON: lambda: 1.2,
            TimeOfDay.EVENING: lambda: 0.8
        },
        "air_quality": {
            WeatherCondition.SUNNY: lambda: 1.1,
            WeatherCondition.PARTLY_CLOUDY: lambda: 1.0,
            WeatherCondition.CLOUDY: lambda: 1.0,
            WeatherCondition.OVERCAST: lambda: 0.9,
            WeatherCondition.LIGHT_RAIN: lambda: 0.9,
            WeatherCondition.RAINY: lambda: 0.8,
            WeatherCondition.HEAVY_RAIN: lambda: 0.7,
            WeatherCondition.STORMY: lambda: 0.6,
            WeatherCondition.LIGHT_SNOW: lambda: 1.2,
            WeatherCondition.SNOWY: lambda: 1.3,
            WeatherCondition.HEAVY_SNOW: lambda: 1.4,
            WeatherCondition.FOGGY: lambda: 1.1,
            WeatherCondition.WINDY: lambda: 0.9
        }
    }
    
    if sensor_type in modifiers:
        if sensor_type == "motion":
            return modifiers[sensor_type][time_of_day]()
        else:
            return modifiers[sensor_type][env_state.weather_condition]()
    return 1.0  # Default modifier if sensor type not found
