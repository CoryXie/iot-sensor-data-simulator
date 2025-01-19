from model.models import DeviceModel
from model.sensor import Sensor
from utils.iot_hub_helper import IoTHubHelper
from models.base import db_session
from loguru import logger


class Device(DeviceModel):
    '''This class represents a device. A device is a collection of sensors.'''

    @classmethod
    def get_all(cls):
        '''Returns all devices'''
        devices = db_session.query(cls).all()
        logger.debug(f"Retrieved {len(devices)} devices")
        return devices

    @classmethod
    def get_all_by_ids(cls, ids):
        '''Returns all devices with the given ids'''
        devices = db_session.query(cls).filter(cls.id.in_(ids)).all()
        logger.debug(f"Retrieved {len(devices)} devices by IDs: {ids}")
        return devices
    
    @classmethod
    def get_by_id(cls, id):
        '''Returns a device by its id'''
        device = db_session.query(cls).filter_by(id=id).first()
        logger.debug(f"Retrieved device by ID {id}: {device.name if device else 'not found'}")
        return device
    
    @classmethod
    def get_all_unassigned(cls):
        '''Returns all devices that are not assigned to a container'''
        devices = db_session.query(cls).filter(cls.container_id == None).all()
        logger.debug(f"Retrieved {len(devices)} unassigned devices")
        return devices

    @classmethod
    def add(cls, sensor_ids, **kwargs):
        '''Adds a new device to the database'''
        device_client = kwargs.get("device_client") # Usually only set when connected to IoT Hub
        device_name = kwargs.get("device_name") # Usually set when not connected to IoT Hub

        logger.info(f"Adding new device: {device_name if device_name else 'from device client'}")
        try:
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
                logger.debug(f"Created device from IoT Hub client: {device_client.device_id}")
            elif device_name:
                # Create device in database
                device_db = cls(name=device_name)
                logger.debug(f"Created device with name: {device_name}")

            if device_db is not None:
                # Add device to database
                db_session.add(device_db)
                db_session.commit()
                device_db.create_relationship_to_sensors(sensor_ids)
                logger.info(f"Successfully added device {device_db.name} with {len(sensor_ids)} sensors")
                return device_db
            return None
        except Exception as e:
            logger.exception(f"Failed to add device: {str(e)}")
            raise
    
    @classmethod
    def check_if_name_in_use(cls, name):
        '''Checks if a device with the given name already exists'''
        exists = db_session.query(cls).filter(cls.name.ilike(name)).first() is not None
        logger.debug(f"Device name '{name}' {'is' if exists else 'is not'} in use")
        return exists

    def create_relationship_to_sensors(self, sensor_ids):
        '''Creates a relationship between the device and the given sensors'''
        logger.debug(f"Creating relationship between device {self.name} and sensors {sensor_ids}")
        sensors = Sensor.get_all_by_ids(sensor_ids)
        for sensor in sensors:
            sensor.device_id = self.id
        Sensor.session.commit()
        logger.debug(f"Successfully created relationships for {len(sensors)} sensors")

    def clear_relationship_to_sensors(self):
        '''Clears the relationship between the device and the sensors'''
        logger.debug(f"Clearing sensor relationships for device {self.name}")
        for sensor in self.sensors:
            sensor.device_id = None
        Sensor.session.commit()
        logger.debug("Sensor relationships cleared")

    def start_simulation(self, interface, callback, **kwargs):
        '''Starts the device simulation'''
        logger.info(f"Starting simulation for device {self.name} with interface {interface}")
        self.interface = interface

        if interface == "iothub":
            self.iot_hub_helper = kwargs.get("iot_hub_helper")
            logger.debug("Using IoT Hub interface")
        elif interface == "mqtt":
            self.mqtt_helper = kwargs.get("mqtt_helper")
            logger.debug("Using MQTT interface")

        self.container_callback = callback

        for sensor in self.sensors:
            sensor.start_simulation(callback=self.send_simulator_data)
        logger.info(f"Started simulation for device {self.name} with {len(self.sensors)} sensors")

    def send_simulator_data(self, sensor, data):
        '''Sends the simulator data to the IoT Hub or MQTT broker. Used as callback for the sensor simulation'''
        try:
            if self.interface == "iothub" and self.iot_hub_helper is not None and self.client is not None:
                self.iot_hub_helper.send_message(self.client, data)
                logger.debug(f"Sent data to IoT Hub for sensor {sensor.name}")
            elif self.interface == "mqtt" and self.mqtt_helper is not None:
                self.mqtt_helper.publish(data=data)
                logger.debug(f"Published data to MQTT for sensor {sensor.name}")
            
            self.container_callback(sensor, data)
        except Exception as e:
            logger.error(f"Error sending simulator data for device {self.name}, sensor {sensor.name}: {str(e)}")

    def delete(self):
        '''Deletes the device'''
        logger.info(f"Deleting device {self.name}")
        try:
            db_session.delete(self)
            db_session.commit()
            logger.info(f"Device {self.name} deleted successfully")
        except Exception as e:
            logger.exception(f"Error deleting device {self.name}: {str(e)}")
            raise
