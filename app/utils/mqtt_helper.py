from nicegui import ui
from model.option import Option
from utils.response import Response
import paho.mqtt.client as mqtt
import json
import os


class MQTTHelper():
    '''Helper class to send data to a MQTT broker'''

    def __init__(self, topic, container_id=None):
        '''Initializes the MQTT helper'''
        self.topic = topic
        self.is_connected = False
        self.broker_address = os.getenv("MQTT_BROKER_ADDRESS")
        self.broker_port = os.getenv("MQTT_BROKER_PORT")

        # Check if broker address and port are set
        if self.broker_address is None or self.broker_port is None:
            ui.notify("MQTT-Broker not configured", type="negative")
            return

        # Check if broker port is valid
        try:
            self.broker_port = int(self.broker_port)
        except ValueError:
            ui.notify("Provided port is invalid", type="negative")

        # Create MQTT client
        client_id = f"container-{container_id}" if container_id else None
        self.client = mqtt.Client(client_id=client_id)
        
    def connect(self):
        '''Connects to the MQTT broker'''

        # Check if client is initialized
        if self.client is None:
            return

        # Set authentication credentials
        credentials = self.get_auth_credentials()
        if credentials is not None:
            self.client.username_pw_set(credentials["username"], credentials["password"])

        # Connect to broker
        try:
            self.client.on_connect = self._on_connect
            self.client.connect(self.broker_address, self.broker_port)
            self.client.loop_start()
        except ConnectionRefusedError as e:
            return Response(False, f"Connection to MQTT broker refused")
        except Exception as e:
            return Response(False, f"Connection to MQTT broker failed: {e}")
        else:
            return Response(True, "Successfully connected to MQTT broker")
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True

    def publish(self, data):
        '''Publish data to a MQTT topic'''

        # Check if client is connected
        if self.client is None or self.is_connected is False:
            return Response(False, "MQTT-Client not connected")
        
        # Prevent sending messages in demo mode
        is_demo_mode = Option.get_boolean('demo_mode')
        if is_demo_mode:
            return Response(False, "Demo mode active. Messages will not be sent.")
        
        # Prevent manipulation of original data used in other places
        data_copy = data.copy()
        
        # Convert datetime to ISO format
        data_copy["timestamp"] = data_copy["timestamp"].isoformat()

        # Remove sendDuplicate flag
        send_duplicate = data_copy.get("sendDuplicate", False)
        data_copy.pop("sendDuplicate", None)

        # Convert the dictionary to JSON string
        message = json.dumps(data_copy)

        # Publish message
        for _ in range(1 if not send_duplicate else 2):
            print(f"Sending message '{message}' to topic '{self.topic}'")
            self.client.publish(self.topic, message)

        return Response(True, "Message sent successfully")

    def disconnect(self):
        '''Disconnects from the MQTT broker'''
        if self.client is None:
            print("MQTT-Client not connected")
            return False

        self.client.disconnect()

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

