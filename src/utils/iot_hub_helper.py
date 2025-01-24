import paho.mqtt.client as mqtt
from src.models.option import Option
from src.utils.response import Response
import json
import os
import re
import ssl
from datetime import datetime

class IoTHubHelper:
    def __init__(self):
        '''Initializes the IoT Hub helper.'''
        self.client = None
        self.host_name = self.get_host_name()

    def create_device(self, device_id):
        '''
        Note: Device management will need to be done through Azure Portal 
        or Azure CLI since we removed the IoT Hub SDK
        '''
        return Response(False, "Device management requires Azure Portal or Azure CLI. Please create the device manually.")

    def delete_device(self, device_id, etag=None):
        '''
        Note: Device management will need to be done through Azure Portal 
        or Azure CLI since we removed the IoT Hub SDK
        '''
        return Response(False, "Device management requires Azure Portal or Azure CLI. Please delete the device manually.")

    def create_device_client(self, connection_string):
        '''Creates an MQTT client using the connection string'''
        try:
            # Parse connection string
            cs_args = dict(arg.split('=', 1) for arg in connection_string.split(';'))
            device_id = cs_args.get('DeviceId')
            shared_access_key = cs_args.get('SharedAccessKey')
            host_name = cs_args.get('HostName')

            if not all([device_id, shared_access_key, host_name]):
                return None

            # Create MQTT client
            client = mqtt.Client(client_id=device_id, protocol=mqtt.MQTTv311)
            
            # Set username and password
            username = f"{host_name}/{device_id}/?api-version=2021-04-12"
            client.username_pw_set(username, shared_access_key)

            # Enable SSL/TLS
            client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)
            client.tls_insecure_set(False)

            # Connect to IoT Hub
            client.connect(host_name, port=8883)
            client.loop_start()

            self.client = client
            return client

        except Exception as e:
            print(f"Error creating MQTT client: {e}")
            return None

    def send_message(self, device_client, data):
        '''Sends a message using MQTT'''
        # Prevent sending messages in demo mode
        is_demo_mode = Option.get_boolean('demo_mode')
        if is_demo_mode:
            return Response(False, "Demo mode active. Messages will not be sent.")

        # Prevent manipulation of original data
        data_copy = data.copy()
        
        # Convert datetime to ISO format
        data_copy["timestamp"] = data_copy["timestamp"].isoformat()

        # Remove sendDuplicate flag
        send_duplicate = data_copy.get("sendDuplicate", False)
        data_copy.pop("sendDuplicate", None)

        try:
            # Convert the dictionary to JSON string
            json_data = json.dumps(data_copy)
            
            # MQTT topic for device-to-cloud messages
            topic = f"devices/{device_client._client_id}/messages/events/"
            
            # Send message (once or twice if duplicate)
            for _ in range(1 if not send_duplicate else 2):
                result = device_client.publish(topic, json_data, qos=1)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    raise Exception(f"Failed to publish message: {result.rc}")
                
            return Response(True, "Message sent successfully")

        except Exception as e:
            return Response(False, f"Error sending message: {str(e)}")

    @staticmethod
    def get_host_name():
        '''Returns the host name of the IoT Hub from the connection string.'''
        try:
            connection_string = os.getenv("IOT_HUB_CONNECTION_STRING")
            host_name = re.search('HostName=(.+?).azure-devices.net', connection_string).group(1)
        except (AttributeError, TypeError):
            host_name = None
        
        return host_name