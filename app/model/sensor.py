from model.models import SensorModel
from utils.simulator import Simulator
import threading
from models.base import db_session


class Sensor(SensorModel):
    '''This class represents a sensor.'''

    @classmethod
    def add(cls, name, base_value, unit, variation_range, change_rate, interval, error_definition, device_id):
        '''Adds a new sensor to the database'''
        new_sensor = cls(name=name, base_value=base_value,
                        unit=unit, variation_range=variation_range, change_rate=change_rate, interval=interval, error_definition=error_definition, device_id=device_id)

        db_session.add(new_sensor)
        db_session.commit()

        return new_sensor

    @classmethod
    def get_all(cls):
        '''Returns all sensors'''
        return db_session.query(cls).all()

    @classmethod
    def get_all_by_ids(cls, list_of_ids):
        '''Returns all sensors with the given ids'''
        return db_session.query(cls).filter(cls.id.in_(list_of_ids)).all()
    
    @classmethod
    def get_by_id(cls, id):
        '''Returns a sensor by its id'''
        return db_session.query(cls).filter(cls.id == id).first()

    @classmethod
    def get_all_unassigned(cls):
        '''Returns all sensors that are not assigned to a device'''
        return db_session.query(cls).filter(cls.device_id == None).all()
    
    @classmethod
    def check_if_name_in_use(cls, name):
        '''Checks if a sensor with the given name already exists'''
        return db_session.query(cls).filter(cls.name.ilike(name)).first() is not None
    
    def start_simulation(self, callback):
        '''Starts the simulation'''
        self.simulator = Simulator(sensor=self)
        self.running = True

        timer = threading.Timer(interval=self.interval, function=self._callback, args=[callback])
        timer.start()

    def _callback(self, device_callback):
        '''Callback function for the simulation'''

        # Check if simulation is still running
        if self.running:
            data = self.simulator.generate_data()
            device_callback(self, data)

            # Repeat callback after interval
            timer = threading.Timer(
                interval=self.interval, function=self._callback, args=[device_callback])
            timer.start()

    def stop_simulation(self):
        '''Stops the simulation'''
        self.running = False

    def start_bulk_simulation(self, amount):
        '''Starts a bulk simulation and returns the generated data'''
        simulator = Simulator(sensor=self)
        data = simulator.generate_bulk_data(amount)
        return data

    def delete(self):
        '''Deletes the sensor'''
        db_session.delete(self)
        db_session.commit()
