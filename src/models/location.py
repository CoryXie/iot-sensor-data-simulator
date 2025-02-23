"""Location model for weather data"""
from dataclasses import dataclass

@dataclass
class Location:
    """Location data class"""
    country: str
    region: str
    timezone: str = "UTC"
