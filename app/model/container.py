from model.models import ContainerModel
from model.device import Device
from utils.mqtt_helper import MQTTHelper
from utils.container_thread import ContainerThread
from constants.units import *
from nicegui import ui
import datetime
from models.base import db_session
from loguru import logger


class Container(ContainerModel):
    '''This class represents a container. A container is a collection of devices.'''

    message_count = None
    device_clients = {}
    thread = None

    def __init__(self, *args, **kwargs):
        '''Initializes the container'''
        super().__init__(*args, **kwargs)
        self.thread = None
        logger.debug(f"Initialized container: {self.name if hasattr(self, 'name') else 'unnamed'}")

    @classmethod
    def get_all(cls):
        '''Returns all containers'''
        containers = db_session.query(cls).all()
        logger.debug(f"Retrieved {len(containers)} containers")
        return containers
    
    @classmethod
    def get_by_id(cls, id):
        '''Returns a container by its id'''
        container = db_session.query(cls).filter(cls.id == id).first()
        logger.debug(f"Retrieved container by ID {id}: {container.name if container else 'not found'}")
        return container

    def get_device_count(self):
        '''Returns the number of devices in the container'''
        count = len(self.devices)
        logger.debug(f"Container {self.name} has {count} devices")
        return count

    def get_devices(self):
        '''Returns all devices in the container'''
        devices = self.devices
        logger.debug(f"Retrieved {len(devices)} devices for container {self.name}")
        return devices

    @classmethod
    def add(cls, name, description, location, device_ids):
        '''Adds a new container to the database'''
        logger.info(f"Adding new container: {name}")
        try:
            container_db = cls(name=name, description=description,
                            location=location, is_active=False, start_time=None)
            db_session.add(container_db)
            db_session.commit()
            container_db.create_relationship_to_devices(device_ids)
            logger.info(f"Successfully added container {name} with {len(device_ids)} devices")
            return container_db
        except Exception as e:
            logger.error(f"Failed to add container {name}: {str(e)}")
            raise

    @staticmethod
    def check_if_name_in_use(name):
        '''Checks if a container with the given name already exists'''
        exists = Container.session.query(Container).filter(Container.name.ilike(name)).first() is not None
        logger.debug(f"Container name '{name}' {'is' if exists else 'is not'} in use")
        return exists

    def create_relationship_to_devices(self, device_ids):
        '''Creates a relationship between the container and the given devices'''
        logger.debug(f"Creating relationship between container {self.name} and devices {device_ids}")
        devices = Device.get_all_by_ids(device_ids)
        for device in devices:
            device.container_id = self.id
        Container.session.commit()
        logger.debug(f"Successfully created relationships for {len(devices)} devices")

    def start(self, interface, success_callback, **kwargs):
        '''Starts the container simulation'''
        logger.info(f"Starting container {self.name} with interface {interface}")
        iot_hub_helper = kwargs.get("iot_hub_helper")
        mqtt_helper = None

        if interface == "iothub" and iot_hub_helper is None:
            logger.error("IoT Hub Helper is not initialized")
            ui.notify("IoT Hub Helper ist nicht initialisiert!", type="negative")
            return
        elif interface == "mqtt":
            mqtt_helper = MQTTHelper(topic=self.name, container_id=self.id)
            response = mqtt_helper.connect()
            
            if response is None:
                logger.error("MQTT credentials are not set")
                return
            else:
                logger.info(f"MQTT connection response: {response.message}")
                ui.notify(response.message, type="positive" if response.success else "negative")

                if not response.success:
                    return

        # Update container status
        self.is_active = True
        self.start_time = datetime.datetime.now()
        Container.session.commit()
        logger.info(f"Container {self.name} marked as active")

        # Start container thread
        self.thread = ContainerThread(target=self._thread_function, kwargs={"interface": interface, "iot_hub_helper": iot_hub_helper, "mqtt_helper": mqtt_helper,  "success_callback": success_callback})
        self.thread.start()
        logger.debug("Container thread started")

    def _thread_function(self, *args, **kwargs):
        '''Thread function for running the container simulation'''
        interface = kwargs.get("interface")
        iot_hub_helper = kwargs.get("iot_hub_helper")
        mqtt_helper = kwargs.get("mqtt_helper")
        success_callback = kwargs.get("success_callback")

        logger.debug(f"Starting thread function for container {self.name}")

        if interface == "iothub":
            device_clients = self._connect_device_clients(iot_hub_helper)
            for device in self.devices:
                device.start_simulation(interface, self._message_callback, iot_hub_helper=iot_hub_helper)
        elif interface == "mqtt":
            for device in self.devices:
                device.start_simulation(interface, self._message_callback, mqtt_helper=mqtt_helper)

        self.message_count = 0
        success_callback(self)

        # Run simulation
        logger.debug(f"Container {self.name} simulation running")
        while not self.thread.stopped():
            pass

        # Stop Container
        if interface == "iothub":
            self._disconnect_device_clients(device_clients)

        self._reset_container_status()
        logger.info(f"Container {self.name} thread function completed")
    
    def _connect_device_clients(self, iot_hub_helper):
        '''Connects all devices to the IoT Hub and returns a list of device clients'''
        logger.debug(f"Connecting devices for container {self.name} to IoT Hub")
        clients = []

        for device in self.devices:
            if device.connection_string is None:
                logger.warning(f"Device {device.name} has no connection string")
                continue

            device_client = iot_hub_helper.init_device_client(device.connection_string)
            device.client = device_client
            clients.append(device_client)
            logger.debug(f"Connected device {device.name} to IoT Hub")

        logger.info(f"Connected {len(clients)} devices to IoT Hub")
        return clients

    def _disconnect_device_clients(self, clients):
        '''Disconnects all device clients'''
        logger.debug(f"Disconnecting {len(clients)} device clients for container {self.name}")
        for client in clients:
            client.disconnect()
        self.device_clients = None
        for device in self.devices:
            device.client = None
        logger.info("All device clients disconnected")

    def _reset_container_status(self):
        '''Resets the container status'''
        logger.debug(f"Resetting status for container {self.name}")
        self.is_active = False
        self.start_time = None
        Container.session.commit()
        logger.debug("Container status reset complete")

    def _message_callback(self, sensor, data):
        '''Callback function for receiving messages from the sensors. Updates the live view and the log.'''
        self.message_count += 1

        # Get sensor data relevant for the log and live view
        value = data["value"]
        timestamp = data["timestamp"]
        timestamp_formatted = timestamp.strftime("%H:%M:%S")

        # Get unit abbreviation
        unit = UNITS[int(data['unit'])]
        unit_abbrev = unit["unit_abbreviation"]

        send_duplicate = data.get("sendDuplicate", False)
        for _ in range(2 if send_duplicate else 1):
            # Add data to log and live view
            log_message = f"{timestamp_formatted}: {data['deviceId']} - {data['sensorName']} - {data['value']} {unit_abbrev}"
            logger.debug(f"Container {self.name} received message: {log_message}")
            self.log.push(log_message)
            self.live_view_dialog.append_data_point(sensor, timestamp, value)

    def stop(self):
        '''Stops the container simulation'''
        if not self.is_active:
            logger.debug(f"Container {self.name} is already inactive")
            return

        logger.info(f"Stopping container {self.name}")
        # Stop sensors from generating data
        for sensor in self.get_sensors():
            sensor.stop_simulation()

        try:
            # Stop container thread if it exists
            if hasattr(self, 'thread') and self.thread is not None:
                logger.debug("Stopping container thread")
                self.thread.stop()
                self.thread.join(timeout=5)  # Wait up to 5 seconds for thread to finish
                self.thread = None

            # Reset container state
            self.is_active = False
            self.start_time = None
            self.message_count = None
            Container.session.commit()
            logger.info(f"Container {self.name} stopped successfully")
        except Exception as e:
            logger.exception(f"Error stopping container {self.name}: {str(e)}")
            # Ensure container is marked as stopped even if there's an error
            self.is_active = False
            self.start_time = None
            Container.session.commit()

    def get_sensors(self):
        '''Returns all sensors in the container'''
        sensors = []
        for device in self.devices:
            sensors.extend(device.sensors)
        logger.debug(f"Retrieved {len(sensors)} sensors for container {self.name}")
        return sensors

    def delete(self):
        '''Deletes the container'''
        logger.info(f"Deleting container {self.name}")
        try:
            Container.session.delete(self)
            Container.session.commit()
            logger.info(f"Container {self.name} deleted successfully")
        except Exception as e:
            logger.exception(f"Error deleting container {self.name}: {str(e)}")
            raise
