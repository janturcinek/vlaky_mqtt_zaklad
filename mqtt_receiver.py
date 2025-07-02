# mqtt_receiver.py
import paho.mqtt.client as mqtt
from instance import data_funkce
import struct
from datetime import datetime
import numpy as np
import os


packet_buffers = {}  # Globální buffer pro zprávy

WAVE_SAMPLE_LEN = 1024
format_str = f'<HHHHIIH{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}HH'

class DataPacket:
    def __init__(self, data):
        self.packet_header = data[0]
        self.packet_version = data[1]
        self.actual_packet_nr = data[2]
        self.total_packet_nr = data[3]
        self.timestamp = data[4]
        # + další pole

def on_message(client, userdata, msg):
    global packet_buffers
    unpacked_data = struct.unpack(format_str, msg.payload)
    packet = DataPacket(unpacked_data)

    client_id = msg.topic.split('/')[1] if '/' in msg.topic else "unknown"
    timestamp_str = datetime.fromtimestamp(packet.timestamp).isoformat()
    device_id = data_funkce.registerovano(client_id)
    if not device_id:
        print(f"Packet from unknown device {client_id} ignored")
        return

    key = (device_id, packet.timestamp)
    if key not in packet_buffers:
        packet_buffers[key] = []
    packet_buffers[key].append(msg.payload)

    print(f"Buffered packet {packet.actual_packet_nr}/{packet.total_packet_nr} from {device_id}")

    if packet.actual_packet_nr == packet.total_packet_nr:
        # Zcelení a uložení souboru
        bin_data = b''.join(packet_buffers[key])
        base_path = f"data_storage/{device_id}"
        os.makedirs(base_path, exist_ok=True)
        filename = f"{base_path}/{timestamp_str.replace(':', '-')}.bin"
        with open(filename, "wb") as f:
            f.write(bin_data)

        # Záznam do DB
        data_funkce.uloz_zpravu(device_id, msg.topic, packet.total_packet_nr, filename)

        print(f"Complete message saved to {filename}")

        # Vyčistit buffer
        del packet_buffers[key]

    
def run_mqtt_receiver(app):
    with app.app_context():
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "Flask_MQTT_Receiver")
        client.username_pw_set("iot-course-but", "thisisthemostsecretsecretever")
        client.on_connect = lambda c,u,f,r: print("MQTT Connected!" if r==0 else f"MQTT Fail {r}")
        client.on_message = on_message
        client.connect("iot-course-but.cloud.shiftr.io", 1883)
        client.subscribe("NRF/FF/UP_STREAM")
        client.loop_forever()