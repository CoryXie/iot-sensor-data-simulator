from nicegui import ui
from src.models.option import Option
from src.utils.response import Response
import paho.mqtt.client as mqtt
import json
import os
from loguru import logger


class MQTTHelper():
    '''Helper class to send data to a MQTT broker'''

    _instance = None

    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = MQTTHelper(
                os.getenv('MQTT_BROKER_ADDRESS'),
                int(os.getenv('MQTT_BROKER_PORT', 1883))
            )
        return cls._instance

    def __init__(self, broker_address, broker_port):
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.topic = ""
        self.qos = 0
        self.retain = False
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_publish = self._on_publish
        self.connect()

    def connect(self):
        try:
            logger.info(f"Connecting to MQTT broker at {self.broker_address}:{self.broker_port}")
            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.loop_start()
            logger.info("Connected to MQTT broker")
        except Exception as e:
            logger.error(f"MQTT Connection Error: {str(e)}")

    def disconnect_from_broker(self):
        '''Disconnects from the MQTT broker'''
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")

    def publish(self, payload):
        '''Publishes a message to the MQTT broker'''
        try:
            self.client.publish(self.topic, payload=payload, qos=self.qos, retain=self.retain)
        except Exception as e:
            logger.error(f"Error publishing to MQTT broker: {e}")

    def publish_sensor_data(self, sensor_data):
        """Publish sensor data to MQTT topic"""
        try:
            topic = f"smart_home/{sensor_data['room']}/{sensor_data['sensor_type']}"
            self.client.publish(topic, json.dumps(sensor_data))
            logger.debug(f"Published to {topic}: {sensor_data['value']}")
        except Exception as e:
            logger.error(f"MQTT Publish Error: {str(e)}")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.debug(f"Connected to MQTT broker, topic: {self.topic}")
        else:
            logger.error(f"MQTT Connection failed with code {rc}")

    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published (MID: {mid})")

    def get_auth_credentials(self):
        '''Returns the authentication credentials for the MQTT broker'''
        username = os.getenv("MQTT_BROKER_USERNAME")
        password = os.getenv("MQTT_BROKER_PASSWORD")

        if username is None or password is None:
            return None
        
        return {
            "username": username,
            "password": password
        }

    @staticmethod
    def get_broker_address():
        '''Returns the MQTT broker address'''
        return os.getenv("MQTT_BROKER_ADDRESS")
    
    @staticmethod
    def get_broker_port():
        '''Returns the MQTT broker port'''
        return os.getenv("MQTT_BROKER_PORT")
    
    @staticmethod
    def is_configured():
        '''Returns True if the MQTT broker is configured'''
        return os.getenv("MQTT_BROKER_ADDRESS") is not None and os.getenv("MQTT_BROKER_PORT") is not None

