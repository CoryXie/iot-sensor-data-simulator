from model.models import DeviceModel
from model.sensor import Sensor
from utils.iot_hub_helper import IoTHubHelper
from models.base import db_session


class Device(DeviceModel):
    '''This class represents a device. A device is a collection of sensors.'''

    @classmethod
    def get_all(cls):
        '''Returns all devices'''
        return db_session.query(cls).all()

    @classmethod
    def get_all_by_ids(cls, ids):
        '''Returns all devices with the given ids'''
        return db_session.query(cls).filter(cls.id.in_(ids)).all()
    
    @classmethod
    def get_by_id(cls, id):
        '''Returns a device by its id'''
        return db_session.query(cls).filter_by(id=id).first()
    
    @classmethod
    def get_all_unassigned(cls):
        '''Returns all devices that are not assigned to a container'''
        return db_session.query(cls).filter(cls.container_id == None).all()

    @classmethod
    def add(cls, sensor_ids, **kwargs):
        '''Adds a new device to the database'''
        device_client = kwargs.get("device_client") # Usually only set when connected to IoT Hub
        device_name = kwargs.get("device_name") # Usually set when not connected to IoT Hub

        device_db = None
        # Create device from device client if connected to IoT Hub
        if device_client:
            # Create connection string for device
            primary_key = device_client.authentication.symmetric_key.primary_key
            host_name = IoTHubHelper.get_host_name()
            connection_string = f"HostName={host_name}.azure-devices.net;DeviceId={device_client.device_id};SharedAccessKey={primary_key}"

            # Create device in database
            device_db = cls(name=device_client.device_id, generation_id=device_client.generation_id,
                          etag=device_client.etag, status=device_client.status, connection_string=connection_string)
        elif device_name:
            # Create device in database
            device_db = cls(name=device_name)

        if device_db is not None:
            # Add device to database
            db_session.add(device_db)
            db_session.commit()
            device_db.create_relationship_to_sensors(sensor_ids)
            return device_db
        return None
    
    @classmethod
    def check_if_name_in_use(cls, name):
        '''Checks if a device with the given name already exists'''
        return db_session.query(cls).filter(cls.name.ilike(name)).first() is not None

    def create_relationship_to_sensors(self, sensor_ids):
        '''Creates a relationship between the device and the given sensors'''
        sensors = Sensor.get_all_by_ids(sensor_ids)
        for sensor in sensors:
            sensor.device_id = self.id
        Sensor.session.commit()

    def clear_relationship_to_sensors(self):
        '''Clears the relationship between the device and the sensors'''
        for sensor in self.sensors:
            sensor.device_id = None
        Sensor.session.commit()

    def start_simulation(self, interface, callback, **kwargs):
        '''Starts the device simulation'''
        self.interface = interface

        if interface == "iothub":
            self.iot_hub_helper = kwargs.get("iot_hub_helper")
        elif interface == "mqtt":
            self.mqtt_helper = kwargs.get("mqtt_helper")

        self.container_callback = callback

        for sensor in self.sensors:
            sensor.start_simulation(callback=self.send_simulator_data)

    def send_simulator_data(self, sensor, data):
        '''Sends the simulator data to the IoT Hub or MQTT broker. Used as callback for the sensor simulation'''
        if self.interface == "iothub" and self.iot_hub_helper is not None and self.client is not None:
            self.iot_hub_helper.send_message(self.client, data)
        elif self.interface == "mqtt" and self.mqtt_helper is not None:
            self.mqtt_helper.publish(data=data)
        
        self.container_callback(sensor, data)

    def delete(self):
        '''Deletes the device'''
        db_session.delete(self)
        db_session.commit()
