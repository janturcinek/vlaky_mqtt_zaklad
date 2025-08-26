# mqtt_receiver.py
import paho.mqtt.client as mqtt
from instance import data_funkce
import struct
from datetime import datetime
import numpy as np
import os
from nastaveni import WAVE_SAMPLE_LEN, format_str
from time import sleep


packet_buffers = {}  # Globální buffer pro zprávy


packet_timestamp_workaround=int(datetime.now().timestamp())
updated_workaround_timestamp=1
timestamp_str=0
on_msg_call_cntr=0

class DataPacket:
    def __init__(self, data):
        self.packet_header = data[0]
        self.packet_version = data[1]
        self.actual_packet_nr = data[2]
        self.total_packet_nr = data[3]
        self.timestamp = data[4]
        
        self.total_sample_count = data[5]
        self.train_counter = data[6]

        base = 7
        self.chan_0_vlt = np.array(data[base : base + WAVE_SAMPLE_LEN], dtype=np.int16)
        self.chan_0_int = np.array(data[base + WAVE_SAMPLE_LEN : base + 2 * WAVE_SAMPLE_LEN], dtype=np.int16)
        self.chan_1_vlt = np.array(data[base + 2 * WAVE_SAMPLE_LEN : base + 3 * WAVE_SAMPLE_LEN], dtype=np.int16)
        self.chan_1_int = np.array(data[base + 3 * WAVE_SAMPLE_LEN : base + 4 * WAVE_SAMPLE_LEN], dtype=np.int16)

        self.CRC = data[base + 4 * WAVE_SAMPLE_LEN]
        

def on_message(client, userdata, msg):
    global packet_buffers
    global updated_workaround_timestamp
    global packet_timestamp_workaround
    global timestamp_str
    global on_msg_call_cntr
    
    on_msg_call_cntr=on_msg_call_cntr+1
    print (f"cntr {on_msg_call_cntr}")
    print("je tu zpráva!")


    unpacked_data = struct.unpack(format_str, msg.payload)
    packet = DataPacket(unpacked_data)
    
    #data_funkce.print_packet_content(packet)
    
    client_id = msg.topic.split('/')[1] if '/' in msg.topic else "unknown"
    #timestamp_str = datetime.fromtimestamp(packet.timestamp).isoformat() #FIXME
    device_id = data_funkce.registerovano(client_id)
    if not device_id:
        print(f"Packet from unknown device {client_id} ignored")
        return

#FIXME
    print (f"original device packet timestamp -> {packet.timestamp}" ) # timestamp bude dobre fungovat pri reception 1 ks modulu, vice modulu problem !!!!!!
    if updated_workaround_timestamp == 1 :
        packet_timestamp_workaround=int(datetime.now().timestamp())
        print (f"generating timestamp from local pc -> {packet_timestamp_workaround}")
        timestamp_str = datetime.fromtimestamp(packet_timestamp_workaround).isoformat()
        updated_workaround_timestamp=0
        
        

    key = (device_id, packet_timestamp_workaround)
    #key = (device_id, packet.timestamp)
    
    # 📦 místo listu použij slovník s číslem paketu jako klíč
    if key not in packet_buffers:
        packet_buffers[key] = {}

    # 📛 pokud už jsme tento paket přijali, přepiš (nepřidávej duplikát)
    packet_buffers[key][packet.actual_packet_nr] = msg.payload

    print(f"Buffered packet {packet.actual_packet_nr}/{packet.total_packet_nr} from {device_id}")

    # ✅ kontrola, že máme všechny pakety
    if len(packet_buffers[key]) == packet.total_packet_nr:
        # seřaď podle klíče (packet ID)
        ordered_packets = [
            packet_buffers[key][i] for i in range(1, packet.total_packet_nr + 1)
        ]
        bin_data = b''.join(ordered_packets)

        base_path = f"data_storage/{device_id}"
        os.makedirs(base_path, exist_ok=True)
        filename = f"{base_path}/{timestamp_str.replace(':', '-')}.bin"
        with open(filename, "wb") as f:
            f.write(bin_data)

        # zápis do databáze
        data_funkce.uloz_zpravu(device_id, msg.topic, packet.total_packet_nr, filename)

        print(f"Complete message saved to {filename}")

        # cleanup
        updated_workaround_timestamp=1
        print ("enable future timestamp workaroud update")
        #sleep(0.5)
        #print ("ende")
        #sleep(0.5)
        del packet_buffers[key]


    
def run_mqtt_receiver(app):
    with app.app_context():
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "Flask_MQTT_Receiver")
        client.username_pw_set("iot-course-but", "thisisthemostsecretsecretever")
        client.on_connect = lambda c,u,f,r: print("MQTT Connected!" if r==0 else f"MQTT Fail {r}")
        client.on_message = on_message
        client.connect("iot-course-but.cloud.shiftr.io", 1883)
        client.subscribe("NRF/+/UP_STREAM")
        client.loop_forever()