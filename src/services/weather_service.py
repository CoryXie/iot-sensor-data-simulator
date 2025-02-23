"""Weather service to fetch real weather data"""
import requests
from datetime import datetime
from typing import Dict, Optional, Union, List
from loguru import logger
import os
from src.models.environmental_factors import WeatherCondition
from dataclasses import dataclass
from enum import Enum

class LocationType(Enum):
    """Types of location queries supported by WeatherAPI"""
    CITY = "city"
    LATLON = "latlon"
    POSTCODE = "postcode"
    IATA = "iata"
    IP = "ip"
    METAR = "metar"

@dataclass
class LocationQuery:
    """Location query parameters"""
    type: LocationType
    value: Union[str, tuple]
    
    def to_query(self) -> str:
        """Convert to API query string"""
        if self.type == LocationType.LATLON:
            lat, lon = self.value
            return f"{lat},{lon}"
        elif self.type == LocationType.IATA:
            return f"iata:{self.value}"
        elif self.type == LocationType.METAR:
            return f"metar:{self.value}"
        elif self.type == LocationType.IP:
            return "auto:ip" if self.value == "auto" else self.value
        else:
            return str(self.value)

class WeatherService:
    """Service to fetch weather data from WeatherAPI.com"""
    
    def __init__(self):
        """Initialize weather service"""
        self.api_key = os.getenv('WEATHERAPI_KEY', '')
        if not self.api_key:
            logger.error("WeatherAPI key not found. Please set WEATHERAPI_KEY environment variable.")
        self.base_url = "http://api.weatherapi.com/v1"
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
        
    def _validate_location_query(self, location_query: LocationQuery) -> bool:
        """Validate location query parameters"""
        if not location_query or not location_query.type or not location_query.value:
            return False
            
        if location_query.type == LocationType.LATLON:
            if not isinstance(location_query.value, tuple) or len(location_query.value) != 2:
                return False
            lat, lon = location_query.value
            try:
                lat, lon = float(lat), float(lon)
                return -90 <= lat <= 90 and -180 <= lon <= 180
            except (ValueError, TypeError):
                return False
                
        return True
        
    def _handle_rate_limits(self, response):
        """Update rate limit information from response headers"""
        try:
            self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))
            
            if self.rate_limit_remaining == 0:
                logger.warning(f"Weather API rate limit reached. Resets in {self.rate_limit_reset} seconds.")
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing rate limit headers: {str(e)}")
            
    def get_weather(self, location_query: LocationQuery, include_aqi: bool = True) -> Optional[Dict]:
        """Get current weather for location"""
        if not self.api_key:
            logger.error("Cannot fetch weather data: WeatherAPI key not set")
            return None
            
        if not self._validate_location_query(location_query):
            logger.error(f"Invalid location query: {location_query}")
            return None
            
        try:
            # Get current weather data
            url = f"{self.base_url}/current.json"
            params = {
                'key': self.api_key,
                'q': location_query.to_query(),
                'aqi': 'yes' if include_aqi else 'no'
            }
            
            response = requests.get(url, params=params)
            self._handle_rate_limits(response)
            
            # Handle common HTTP errors
            if response.status_code == 401:
                logger.error("Invalid WeatherAPI key")
                return None
            elif response.status_code == 403:
                logger.error("API key has expired or been disabled")
                return None
            elif response.status_code == 429:
                logger.error("Rate limit exceeded")
                return None
                
            response.raise_for_status()
            weather_data = response.json()
            
            # Extract relevant data
            current = weather_data['current']
            condition = current['condition']['text']
            
            return {
                'temperature': current['temp_c'],
                'humidity': current['humidity'],
                'pressure': current['pressure_mb'],
                'wind_speed': current['wind_kph'],
                'wind_direction': current['wind_dir'],
                'cloud': current['cloud'],
                'feels_like': current['feelslike_c'],
                'uv': current['uv'],
                'air_quality': {
                    'co': current['air_quality'].get('co', 0),
                    'no2': current['air_quality'].get('no2', 0),
                    'o3': current['air_quality'].get('o3', 0),
                    'pm2_5': current['air_quality'].get('pm2_5', 0),
                    'pm10': current['air_quality'].get('pm10', 0),
                } if include_aqi else {},
                'weather_condition': self._map_weather_condition(condition),
                'description': condition,
                'is_day': bool(current['is_day']),
                'last_updated': current['last_updated'],
                'location': {
                    'name': weather_data['location']['name'],
                    'region': weather_data['location']['region'],
                    'country': weather_data['location']['country'],
                    'lat': weather_data['location']['lat'],
                    'lon': weather_data['location']['lon'],
                    'timezone': weather_data['location']['tz_id'],
                    'localtime': weather_data['location']['localtime']
                }
            }
            
        except Exception as e:
            logger.error(f"Error fetching weather data: {str(e)}")
            return None

    def search_locations(self, query: str) -> List[Dict]:
        """Search for locations using the Search/Autocomplete API"""
        try:
            url = f"{self.base_url}/search.json"
            params = {
                'key': self.api_key,
                'q': query
            }
            
            response = requests.get(url, params=params)
            self._handle_rate_limits(response)
            
            # Handle common HTTP errors
            if response.status_code == 401:
                logger.error("Invalid WeatherAPI key")
                return []
            elif response.status_code == 403:
                logger.error("API key has expired or been disabled")
                return []
            elif response.status_code == 429:
                logger.error("Rate limit exceeded")
                return []
                
            response.raise_for_status()
            locations = response.json()
            
            return [{
                'id': loc['id'],
                'name': loc['name'],
                'region': loc['region'],
                'country': loc['country'],
                'lat': loc['lat'],
                'lon': loc['lon'],
                'url': loc['url'],
                'tz_id': loc.get('tz_id')  # Add timezone ID
            } for loc in locations]
            
        except Exception as e:
            logger.error(f"Error searching locations: {str(e)}")
            return []
            
    def _map_weather_condition(self, condition: str) -> WeatherCondition:
        """Map WeatherAPI.com conditions to our WeatherCondition enum"""
        condition_lower = condition.lower()
        
        # Mapping dictionary for better organization and maintainability
        condition_mappings = {
            WeatherCondition.SUNNY: [
                'sunny', 'clear', 'fine', 'fair', 'bright'
            ],
            WeatherCondition.CLOUDY: [
                'cloudy', 'overcast', 'mist', 'fog', 'hazy', 'partly cloudy'
            ],
            WeatherCondition.RAINY: [
                'rain', 'drizzle', 'shower', 'precipitation', 'wet'
            ],
            WeatherCondition.STORMY: [
                'thunder', 'storm', 'lightning', 'squall', 'tornado', 'hurricane', 'cyclone'
            ],
            WeatherCondition.SNOWY: [
                'snow', 'sleet', 'blizzard', 'ice', 'frost', 'freezing'
            ]
        }
        
        # Find matching weather condition
        for weather_type, keywords in condition_mappings.items():
            if any(keyword in condition_lower for keyword in keywords):
                logger.debug(f"Mapped condition '{condition}' to {weather_type.value}")
                return weather_type
        
        # Log unknown condition and default to cloudy
        logger.warning(f"Unknown weather condition '{condition}', defaulting to CLOUDY")
        return WeatherCondition.CLOUDY
