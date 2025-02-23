"""Environmental factors affecting sensor data simulation"""
from dataclasses import dataclass
from datetime import datetime, time
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
    country: str
    region: str
    timezone: str
    
    @property
    def zone_info(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

@dataclass
class SimulationTime:
    datetime: datetime
    custom_time: Optional[time] = None
    
    @property
    def effective_time(self) -> datetime:
        """Get the effective time for simulation"""
        if self.custom_time:
            return datetime.combine(self.datetime.date(), self.custom_time)
        return self.datetime

@dataclass
class WeatherImpactFactors:
    """Impact factors of weather on sensor readings"""
    temperature_modifier: float  # Celsius modifier
    humidity_modifier: float    # Percentage points modifier
    light_level_modifier: float # Percentage points modifier
    air_quality_modifier: float # AQI points modifier
    noise_level_modifier: float # Decibel modifier
    
    @classmethod
    def get_impact_factors(cls, condition: WeatherCondition) -> 'WeatherImpactFactors':
        """Get impact factors for a given weather condition"""
        IMPACT_MAPPING = {
            WeatherCondition.SUNNY: cls(2.0, -5.0, 20.0, -5.0, 0.0),
            WeatherCondition.PARTLY_CLOUDY: cls(0.5, 0.0, 5.0, 0.0, 0.0),
            WeatherCondition.CLOUDY: cls(-0.5, 5.0, -10.0, 5.0, 0.0),
            WeatherCondition.OVERCAST: cls(-1.0, 10.0, -20.0, 10.0, 0.0),
            WeatherCondition.LIGHT_RAIN: cls(-1.5, 15.0, -30.0, -5.0, 5.0),
            WeatherCondition.RAINY: cls(-2.0, 20.0, -40.0, -10.0, 10.0),
            WeatherCondition.HEAVY_RAIN: cls(-3.0, 25.0, -50.0, -15.0, 15.0),
            WeatherCondition.STORMY: cls(-4.0, 30.0, -60.0, -20.0, 20.0),
            WeatherCondition.LIGHT_SNOW: cls(-5.0, -5.0, -20.0, 5.0, -5.0),
            WeatherCondition.SNOWY: cls(-8.0, -10.0, -30.0, 10.0, -10.0),
            WeatherCondition.HEAVY_SNOW: cls(-12.0, -15.0, -40.0, 15.0, -15.0),
            WeatherCondition.FOGGY: cls(-1.0, 20.0, -40.0, 20.0, -5.0),
            WeatherCondition.WINDY: cls(-1.0, -10.0, -5.0, -10.0, 15.0),
        }
        return IMPACT_MAPPING.get(condition, cls(0.0, 0.0, 0.0, 0.0, 0.0))

@dataclass
class EnvironmentalState:
    weather: WeatherCondition
    time_of_day: TimeOfDay
    temperature_celsius: float
    humidity_percent: float
    light_level_percent: float
    location: Location
    simulation_time: SimulationTime
    
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
        
        # Weather modifiers
        weather_modifiers = WeatherImpactFactors.get_impact_factors(weather)
        
        # Calculate base temperature
        base_temp_range = temp_ranges[time_of_day]
        base_temp = (base_temp_range[0] + base_temp_range[1]) / 2
        
        # Apply weather modifiers
        temp = base_temp + weather_modifiers.temperature_modifier
        humidity = 50 + weather_modifiers.humidity_modifier  # Base humidity of 50%
        light = 50 + weather_modifiers.light_level_modifier  # Base light level of 50%
        
        # Adjust light level based on time of day
        time_light_modifiers = {
            TimeOfDay.NIGHT: 0.1,
            TimeOfDay.MORNING: 0.8,
            TimeOfDay.AFTERNOON: 1.0,
            TimeOfDay.EVENING: 0.4
        }
        light *= time_light_modifiers[time_of_day]
        
        simulation_time = SimulationTime(local_time)
        
        return cls(
            weather=weather,
            time_of_day=time_of_day,
            temperature_celsius=temp,
            humidity_percent=min(100, max(0, humidity)),
            light_level_percent=min(100, max(0, light)),
            location=location,
            simulation_time=simulation_time
        )

    @classmethod
    def from_weather_data(cls, weather_data: dict, location: Location, simulation_time: SimulationTime) -> 'EnvironmentalState':
        """Create environmental state from weather API data"""
        return cls(
            weather=weather_data['weather_condition'],
            time_of_day=cls.get_time_of_day(simulation_time.effective_time),
            temperature_celsius=weather_data['temperature'],
            humidity_percent=weather_data['humidity'],
            light_level_percent=cls._calculate_light_level(
                weather_data['weather_condition'],
                simulation_time.effective_time
            ),
            location=location,
            simulation_time=simulation_time
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
        
        weather_modifier = WeatherImpactFactors.get_impact_factors(weather).light_level_modifier
        return min(100, base_light + weather_modifier)

def get_sensor_value_modifier(env_state: EnvironmentalState, sensor_type: str) -> float:
    """Get modifier for sensor values based on environmental conditions"""
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
            return modifiers[sensor_type][env_state.time_of_day]()
        else:
            return modifiers[sensor_type][env_state.weather]()
    return 1.0  # Default modifier if sensor type not found
