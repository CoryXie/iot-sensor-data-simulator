import time
import json
from azure.iot.device import IoTHubDeviceClient, Message

class IoTHubHelper:
    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.device_client = None
        self.init_device_client()

    def init_device_client(self):
        self.device_client = IoTHubDeviceClient.create_from_connection_string(self.connection_string)

    def close_connection(self):
        self.device_client.shutdown()

    def send_telemetry_messages(self, telemetry_messages):
        try:
            if not self.device_client:
                self.init_device_client()

            print("Start sending telemetry messages")
            for msg in telemetry_messages:
                # Convert the dictionary to JSON string
                json_data = json.dumps(msg)

                # Build the message with JSON telemetry data
                message = Message(json_data)

                # Send the message.
                print("Sending message: {}".format(message))
                self.device_client.send_message(message)
            print("Alle Daten erfolgreich gesendet")
            return Response(True, "Alle Daten erfolgreich gesendet")
            
        except Exception as e:
            print(e)
            return Response(False, "Fehler beim Senden: {}".format(e))

class Response:
    def __init__(self, success, message):
        self.success = success
        self.message = message