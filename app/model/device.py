from model.models import DeviceModel
from model.sensor import Sensor
from utils.iot_hub_helper import IoTHubHelper


class Device(DeviceModel):
    '''This class represents a device. A device is a collection of sensors.'''

    @staticmethod
    def get_all():
        '''Returns all devices'''
        return Device.session.query(Device).all()

    @staticmethod
    def get_all_by_ids(ids):
        '''Returns all devices with the given ids'''
        return Device.session.query(Device).filter(Device.id.in_(ids)).all()
    
    def get_by_id(id):
        '''Returns a device by its id'''
        return Device.session.query(Device).filter_by(id=id).first()
    
    @staticmethod
    def get_all_unassigned():
        '''Returns all devices that are not assigned to a container'''
        return Device.session.query(Device).filter(Device.container_id == None).all()

    @staticmethod
    def add(sensor_ids, **kwargs):
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
            device_db = Device(name=device_client.device_id, generation_id=device_client.generation_id,
                            etag=device_client.etag, status=device_client.status, connection_string=connection_string)
        elif device_name:
            # Create device in database
            device_db = Device(name=device_name)

        if device_db is not None:
            # Add device to database
            Device.session.add(device_db)
            Device.session.commit()

            device_db.create_relationship_to_sensors(sensor_ids)

            return device_db
        
        return None
    
    @staticmethod
    def check_if_name_in_use(name):
        '''Checks if a device with the given name already exists'''
        return Device.session.query(Device).filter(Device.name.ilike(name)).first() is not None

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
        Device.session.delete(self)
        Device.session.commit()
