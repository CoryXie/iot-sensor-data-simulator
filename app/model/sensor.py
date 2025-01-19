from model.models import SensorModel
from utils.simulator import Simulator
import threading
from models.base import db_session
from loguru import logger


class Sensor(SensorModel):
    '''This class represents a sensor.'''

    @classmethod
    def add(cls, name, base_value, unit, variation_range, change_rate, interval, error_definition, device_id):
        '''Adds a new sensor to the database'''
        logger.info(f"Adding new sensor: {name}")
        try:
            new_sensor = cls(name=name, base_value=base_value,
                           unit=unit, variation_range=variation_range, change_rate=change_rate, 
                           interval=interval, error_definition=error_definition, device_id=device_id)

            db_session.add(new_sensor)
            db_session.commit()
            logger.info(f"Successfully added sensor {name} with base value {base_value}")
            return new_sensor
        except Exception as e:
            logger.exception(f"Failed to add sensor {name}: {str(e)}")
            raise

    @classmethod
    def get_all(cls):
        '''Returns all sensors'''
        sensors = db_session.query(cls).all()
        logger.debug(f"Retrieved {len(sensors)} sensors")
        return sensors

    @classmethod
    def get_all_by_ids(cls, list_of_ids):
        '''Returns all sensors with the given ids'''
        sensors = db_session.query(cls).filter(cls.id.in_(list_of_ids)).all()
        logger.debug(f"Retrieved {len(sensors)} sensors by IDs: {list_of_ids}")
        return sensors
    
    @classmethod
    def get_by_id(cls, id):
        '''Returns a sensor by its id'''
        sensor = db_session.query(cls).filter(cls.id == id).first()
        logger.debug(f"Retrieved sensor by ID {id}: {sensor.name if sensor else 'not found'}")
        return sensor

    @classmethod
    def get_all_unassigned(cls):
        '''Returns all sensors that are not assigned to a device'''
        sensors = db_session.query(cls).filter(cls.device_id == None).all()
        logger.debug(f"Retrieved {len(sensors)} unassigned sensors")
        return sensors
    
    @classmethod
    def check_if_name_in_use(cls, name):
        '''Checks if a sensor with the given name already exists'''
        exists = db_session.query(cls).filter(cls.name.ilike(name)).first() is not None
        logger.debug(f"Sensor name '{name}' {'is' if exists else 'is not'} in use")
        return exists

    def start_simulation(self, callback):
        '''Starts the simulation'''
        logger.info(f"Starting simulation for sensor {self.name}")
        self.simulator = Simulator(sensor=self)
        self.running = True

        timer = threading.Timer(interval=self.interval, function=self._callback, args=[callback])
        timer.start()
        logger.debug(f"Started simulation timer for sensor {self.name} with interval {self.interval}")

    def _callback(self, device_callback):
        '''Callback function for the simulation'''
        # Check if simulation is still running
        if self.running:
            try:
                data = self.simulator.generate_data()
                device_callback(self, data)
                logger.debug(f"Generated data for sensor {self.name}: {data.get('value')}")

                # Repeat callback after interval
                timer = threading.Timer(
                    interval=self.interval, function=self._callback, args=[device_callback])
                timer.start()
            except Exception as e:
                logger.error(f"Error in simulation callback for sensor {self.name}: {str(e)}")

    def stop_simulation(self):
        '''Stops the simulation'''
        logger.info(f"Stopping simulation for sensor {self.name}")
        self.running = False

    def start_bulk_simulation(self, amount):
        '''Starts a bulk simulation and returns the generated data'''
        logger.info(f"Starting bulk simulation for sensor {self.name} with {amount} records")
        try:
            simulator = Simulator(sensor=self)
            data = simulator.generate_bulk_data(amount)
            logger.info(f"Generated {len(data)} bulk records for sensor {self.name}")
            return data
        except Exception as e:
            logger.exception(f"Error generating bulk data for sensor {self.name}: {str(e)}")
            raise

    def delete(self):
        '''Deletes the sensor'''
        logger.info(f"Deleting sensor {self.name}")
        try:
            db_session.delete(self)
            db_session.commit()
            logger.info(f"Sensor {self.name} deleted successfully")
        except Exception as e:
            logger.exception(f"Error deleting sensor {self.name}: {str(e)}")
            raise
