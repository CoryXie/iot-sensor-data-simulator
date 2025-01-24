from src.constants.sensor_errors import *
import random
import datetime
import json
from loguru import logger

DRIFT_ITERATIONS = 10

class Simulator:
    '''Simulates sensor data.'''

    def __init__(self, sensor):
        '''Initializes the simulator.'''
        self.sensor = sensor
        self.base_value = sensor.base_value
        self.variation_range = sensor.variation_range
        self.change_rate = sensor.change_rate
        self.last_value = self.base_value
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
            max_change = self.variation_range * self.change_rate
            random_change = random.uniform(-max_change, max_change)
            
            # Ensure value stays within variation range
            new_value = self.last_value + random_change
            min_value = self.base_value - self.variation_range
            max_value = self.base_value + self.variation_range
            
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
                'value': self.base_value,
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

            self.base_value += drift_change
            logger.debug(f"Applied drift change to sensor {self.sensor.name}: {drift_change}")
        return {"value": value}
