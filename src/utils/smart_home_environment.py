import time

class Room:
    def __init__(self, name, thermal_mass, heat_loss_coefficient):
        self.name = name
        self.temperature = 20.0  # Default temperature in Celsius
        self.humidity = 50.0  # Default humidity in percentage
        self.thermal_mass = thermal_mass  # Thermal mass of the room
        self.heat_loss_coefficient = heat_loss_coefficient  # Heat loss coefficient
        self.ac_active = False  # Air conditioner state
        self.thermostat_set_temp = 20.0  # Thermostat set temperature

    def update_temperature(self, outdoor_temp, hvac_power, time_elapsed):
        """Update the room temperature based on outdoor temperature and HVAC power."""
        # Apply Newton's Law of Cooling
        dT = (outdoor_temp - self.temperature) * self.heat_loss_coefficient * time_elapsed
        self.temperature += dT + (hvac_power / self.thermal_mass) * time_elapsed

        # Adjust for air conditioner effect
        if self.ac_active:
            cooling_effect = hvac_power / self.thermal_mass  # Simplified cooling effect
            self.temperature -= cooling_effect * time_elapsed

    def update_humidity(self, outdoor_humidity, hvac_dehumidification_rate, time_elapsed):
        """Update the room humidity based on outdoor humidity and HVAC dehumidification."""
        # Simple model for humidity change
        self.humidity += (outdoor_humidity - self.humidity) * 0.1 - hvac_dehumidification_rate * time_elapsed

    def set_ac(self, active):
        """Set the air conditioner state."""
        self.ac_active = active

    def set_thermostat(self, temperature):
        """Set the thermostat temperature."""
        self.thermostat_set_temp = temperature

class House:
    def __init__(self):
        self.rooms = []  # List of rooms in the house

    def add_room(self, room):
        self.rooms.append(room)

    def update_environment(self, outdoor_temp, outdoor_humidity, hvac_power, time_elapsed):
        """Update all rooms in the house based on outdoor conditions and HVAC power."""
        for room in self.rooms:
            room.update_temperature(outdoor_temp, hvac_power, time_elapsed)
            room.update_humidity(outdoor_humidity, hvac_power * 0.1, time_elapsed)  # Example dehumidification rate

    def run_simulation(self, outdoor_temp, outdoor_humidity, hvac_power, time_step, duration):
        """Run the simulation for a specified duration."""
        for _ in range(int(duration / time_step)):
            self.update_environment(outdoor_temp, outdoor_humidity, hvac_power, time_step)
            # Log or print the current state of each room
            for room in self.rooms:
                print(f"{room.name} - Temp: {room.temperature:.2f}°C, Humidity: {room.humidity:.2f}%")
            time.sleep(time_step)  # Wait for the next time step 