from src.constants.sensor_errors import *
import random
import datetime
import json
from loguru import logger
import time

DRIFT_ITERATIONS = 10

class Simulator:
    '''Simulates sensor data.'''

    def __init__(self, sensor):
        '''Initializes the simulator.'''
        self.sensor = sensor
        self.last_value = sensor.current_value
        logger.debug(f"Initializing simulator for sensor {sensor.name} (ID: {sensor.id})")
        self.iteration = 0
        self.previous_value = sensor.base_value
        self.last_duplicate = -1  # Used to prevent more than one duplicate in a row
        self.drifting = False
        self.error_definition = json.loads(
            sensor.error_definition) if sensor.error_definition else None

    def generate_bulk_data(self, amount):
        '''Generates a list of data records.'''
        logger.debug(f"Generating {amount} bulk data records for sensor {self.sensor.name}")
        # Define the start time and interval
        records = []
        start_time = datetime.datetime.now()
        interval = self.sensor.interval

        # Generate the data
        for i in range(amount):
            # Calculate the timestamp
            timestamp = (start_time + datetime.timedelta(seconds=i * interval))
            record = self.generate_data(timestamp=timestamp)
            
            # Handle duplicate data error
            send_duplicate = record["sendDuplicate"]
            del record["sendDuplicate"]
            records.append(record)

            # Append duplicate data if necessary
            if send_duplicate:
                records.append(record)

        return records

    def generate_data(self, **kwargs):
        '''Generates a single data record.'''
        try:
            # Calculate new value based on last value and parameters
            max_change = self.sensor.variation_range * self.sensor.change_rate
            random_change = random.uniform(-max_change, max_change)
            
            # Ensure value stays within variation range
            new_value = self.last_value + random_change
            min_value = self.sensor.base_value - self.sensor.variation_range
            max_value = self.sensor.base_value + self.sensor.variation_range
            
            # Clamp value to valid range
            new_value = max(min_value, min(new_value, max_value))
            self.last_value = new_value
            
            logger.debug(f"Generated value {new_value:.2f} for sensor {self.sensor.name}")

            send_duplicate = False
            if self.error_definition:
                result = self._handle_error_definition(new_value)
                new_value = result["value"]
                send_duplicate = result.get("duplicate", False)

            # Check if None. Errors might change the value to None
            if new_value is not None:
                new_value = round(new_value, 2)
            self.iteration += 1
            if kwargs.get("timestamp") is None:
                timestamp = datetime.datetime.now().isoformat()
            else:
                timestamp = kwargs.get("timestamp")

            # Return the data record with typical characteristics of an IoT sensor
            return {"timestamp": timestamp, "sensorId": self.sensor.id, "sensorName": self.sensor.name, "value": new_value, "unit": self.sensor.unit, "deviceId": self.sensor.device_id, "deviceName": self.sensor.device.name, "sendDuplicate": send_duplicate}
            
        except Exception as e:
            logger.error(f"Error generating data for sensor {self.sensor.name}: {str(e)}")
            return {
                'value': self.sensor.base_value,
                'timestamp': datetime.datetime.now().isoformat()
            }

    def _handle_error_definition(self, value):
        '''Handles the error definition of a sensor.'''
        error_type = self.error_definition["type"]
        logger.debug(f"Handling error type {error_type} for sensor {self.sensor.name}")

        if error_type == ANOMALY:
            return self._handle_anomaly_error(value)
        elif error_type == MCAR:
            return self._handle_mcar_error(value)
        elif error_type == DUPLICATE_DATA:
            return self._handle_duplicate_data_error(value)
        elif error_type == DRIFT:
            return self._handle_drift_error(value)

        return {"value": value}

    def _handle_anomaly_error(self, value):
        '''Handles the anomaly error type.'''
        if random.random() > 1 - self.error_definition[PROBABILITY_POS_ANOMALY]:
            # Add a random positive anomaly
            value += random.uniform(self.error_definition[POS_ANOMALY_LOWER_RANGE],
                                    self.error_definition[POS_ANOMALY_UPPER_RANGE])
            logger.debug(f"Generated positive anomaly for sensor {self.sensor.name}: {value}")

        if random.random() < self.error_definition[PROBABILITY_NEG_ANOMALY]:
            # Add a random negative anomaly
            value -= random.uniform(self.error_definition[NEG_ANOMALY_LOWER_RANGE],
                                    self.error_definition[NEG_ANOMALY_UPPER_RANGE])
            logger.debug(f"Generated negative anomaly for sensor {self.sensor.name}: {value}")

        return {"value": value}

    def _handle_mcar_error(self, value):
        '''Handles the MCAR error type.'''
        if random.random() < self.error_definition[PROBABILITY]:
            # Set value to None
            logger.debug(f"Generated MCAR error for sensor {self.sensor.name}")
            return {"value": None}
        return {"value": value}

    def _handle_duplicate_data_error(self, value):
        '''Handles the duplicate data error type.'''
        if self.iteration - self.last_duplicate > 2 and random.random() < self.error_definition[PROBABILITY]:
            self.last_duplicate = self.iteration
            logger.debug(f"Generated duplicate data for sensor {self.sensor.name}")
            return {"value": value, "duplicate": True}
        return {"value": value}

    def _handle_drift_error(self, value):
        '''Handles the drift error type.'''
        # Init drift after n iterations
        after_n_iterations = self.error_definition[AFTER_N_ITERATIONS]
        if self.drifting or after_n_iterations > self.iteration:
            self.drifting = True

            # Only drift every n iterations
            if self.iteration % DRIFT_ITERATIONS != 0:
                return {"value": value}

            # Calculate the drift change
            average_drift_rate = self.error_definition[AVERAGE_DRIFT_RATE]
            variation_range = self.error_definition[VARIATION_RANGE]
            deviation = random.uniform(-variation_range, variation_range)
            drift_change = average_drift_rate + deviation

            self.sensor.base_value += drift_change
            logger.debug(f"Applied drift change to sensor {self.sensor.name}: {drift_change}")
        return {"value": value}

    def validate_value(self, value):
        """Validate sensor value against allowed range"""
        try:
            min_val = self.sensor.base_value - self.sensor.variation_range
            max_val = self.sensor.base_value + self.sensor.variation_range
            
            # Handle boolean-like sensors (motion, door)
            if self.sensor.type in ['motion', 'door']:
                if value not in (0, 1):
                    logger.warning(f"Invalid value {value} for boolean sensor {self.sensor.name}")
                    raise ValueError(f"Invalid value {value} for boolean sensor {self.sensor.name}")
            
            # Validate numeric sensors
            elif not (min_val <= value <= max_val):
                logger.warning(f"Value {value} out of range [{min_val}-{max_val}] for sensor {self.sensor.name}")
                raise ValueError(f"Value {value} out of range [{min_val}-{max_val}] for sensor {self.sensor.name}")
                
            return True
        except Exception as e:
            logger.error(f"Error validating value: {e}")
            return False

    def _calculate_simulated_value(self):
        """Calculate simulated value based on sensor type"""
        # Implementation of _calculate_simulated_value method
        pass

    def generate_value(self):
        """Generate a new simulated value, handling errors."""
        try:
            # Get the base value to work with
            base = self.last_value if self.last_value is not None else self.sensor.base_value
            
            # Calculate random variation
            variation = random.uniform(-self.sensor.variation_range, self.sensor.variation_range)
            
            # Apply change rate
            new_value = base + (variation * self.sensor.change_rate)
            
            # Clamp to min/max
            new_value = max(self.sensor.min_value, min(self.sensor.max_value, new_value))
            
            # Round based on type
            if self.sensor.type in ['temperature']:
                new_value = round(new_value, 1)
            elif self.sensor.type in ['humidity', 'light']:
                new_value = round(new_value, 0)
            elif self.sensor.type in ['motion', 'door']:
                new_value = 1 if new_value > (self.sensor.max_value / 2) else 0
            else:
                new_value = round(new_value, 2)
            
            self.last_value = new_value  # Update last_value
            return new_value
            
        except Exception as e:
            logger.error(f"Error generating simulated value: {e}")
            return self.sensor.base_value

    def apply_error(self, value):
        """Applies the error definition to the sensor value."""
        if self.error_definition:
            error_type = self.error_definition["type"]
            if error_type == ANOMALY:
                return self._handle_anomaly_error(value)
            elif error_type == MCAR:
                return self._handle_mcar_error(value)
            elif error_type == DUPLICATE_DATA:
                return self._handle_duplicate_data_error(value)
            elif error_type == DRIFT:
                return self._handle_drift_error(value)
        return {"value": value}  # Return original if no error
