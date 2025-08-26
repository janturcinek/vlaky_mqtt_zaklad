import paho.mqtt.client as mqtt
import json
import csv
import sys
import os
from datetime import datetime
import os.path
from time import sleep

import struct
import time
import platform
import subprocess

import numpy as np
from scipy.io import savemat
import math

import ctypes

# Broker vizualizace je nyni public, tak by to melo byt videt
# https://iot-course-but.cloud.shiftr.io/

CLIENT_NAME = "NRF_FAKE_PUBLISHER"
#CLIENT_NAME = "NRF_FAKE_PUBLISHER_1"
HOST = "iot-course-but.cloud.shiftr.io"
PORT = 1883
TOPIC = "NRF/KK/DOWN_STREAM"
PUB_TOPIC = "NRF/KK/UP_STREAM"

WAVE_SAMPLE_LEN = 1024
class DataPacket(ctypes.LittleEndianStructure):
    _pack_ = 1  # Ensures packed structure (no padding)
    _fields_ = [
        ("packet_header", ctypes.c_uint16),
        ("packet_version", ctypes.c_uint16),
        ("actual_packet_nr", ctypes.c_uint16),
        ("total_packet_nr", ctypes.c_uint16),
        ("timestamp", ctypes.c_uint32),
        ("total_sample_count", ctypes.c_uint32),
        ("train_counter", ctypes.c_uint16),

        ("chan_0_vlt", ctypes.c_uint16 * WAVE_SAMPLE_LEN),
        ("chan_0_int", ctypes.c_uint16 * WAVE_SAMPLE_LEN),
        ("chan_1_vlt", ctypes.c_uint16 * WAVE_SAMPLE_LEN),
        ("chan_1_int", ctypes.c_uint16 * WAVE_SAMPLE_LEN),

        ("CRC", ctypes.c_uint16),
    ]

now = datetime.now()
packet = DataPacket()

def prepare_connect_and_run_mqtt_client():
    # Oprava pro paho-mqtt 2.x
    client_instance = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, CLIENT_NAME)

    client_instance.username_pw_set(username="iot-course-but", password="thisisthemostsecretsecretever")
    client_instance.on_connect = on_connect
    client_instance.connect(HOST, PORT)

    client_instance.on_connect_fail = on_fail
    client_instance.subscribe(TOPIC)
    client_instance.loop_forever()

    return client_instance

def on_connect(client, userdata, flags, rc):
    global packet
    if rc == 0:
        print("Connected to MQTT Broker!")
        sleep(2)
        if client.is_connected() == True:
            print("sending multiple packets")

            packet.total_packet_nr = 8  # EDIT PCKTS SEND AMOUNT

            packet.total_sample_count = 1024 * packet.total_packet_nr

            for i in range(1, packet.total_packet_nr + 1):
                packet.actual_packet_nr = i
                packet_bytes = bytes(packet)
                client.publish(PUB_TOPIC, packet_bytes, qos=0, retain=False)
                print("PKT " + str(i) + "/" + str(packet.total_packet_nr) + "  sent")
                sleep(0.1)
            sleep(1)
            client.disconnect()
    else:
        print("Failed to connect, return code %d\n", rc)

def on_disconnect(client_instance, obj, rc):
    client_instance.user_data_set(obj + 1)
    if obj == 0:
        client_instance.reconnect()
        print("reconnecting to Broker")

def on_fail(client_instance, obj):
    print("on_fail_occured")
    client_instance.disconnect()
    check_connection_till_works()
    time.sleep(1)
    prepare_connect_and_run_mqtt_client()

def test_ping_to_server(host):
    parameter = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', parameter, '1', host]
    response = subprocess.call(command)
    now = datetime.now()
    print(str(now.strftime("%Y-%m-%d %H:%M:%S")) + " --> test ping to  " + HOST)
    if response == 0:
        return True
    else:
        return False

def check_connection_till_works():
    while True:
        retval = test_ping_to_server(HOST)
        print(retval)
        now = datetime.now()
        if retval == True:
            print(str(now.strftime("%Y-%m-%d %H:%M:%S")) + " --> response from " + HOST + " was received")
            break
        else:
            print(str(now.strftime("%Y-%m-%d %H:%M:%S")) + " --> response from " + HOST + " not received, next try after 5 sec")
            time.sleep(5)

def main():
    print("program start")

    packet.packet_header = 0xBEEF
    packet.packet_version = 0x11
    packet.actual_packet_nr = 1
    packet.total_packet_nr = 8
    packet.timestamp = int(now.timestamp())
    packet.total_sample_count = 1024
    packet.train_counter = 5
    packet.CRC = 0xFFFF

    num_samples = 1024
    amplitude = 65535 / 2  # Max value for uint16 is 65535
    offset = amplitude  # Shift sine wave to positive range
    x = np.linspace(0, 2 * np.pi, num_samples, endpoint=False)
    sine_wave = np.sin(x)
    output = np.uint16((sine_wave * amplitude) + offset)
    SineWaveArrayType = ctypes.c_ushort * num_samples
    packet.chan_0_vlt = SineWaveArrayType(*output)

    amplitude = 10000 / 2  # Max value for uint16 is 65535
    offset = amplitude  # Shift sine wave to positive range
    x = np.linspace(0, 4 * np.pi, num_samples, endpoint=False)
    sine_wave = np.sin(x)
    output = np.uint16((sine_wave * amplitude) + offset)
    SineWaveArrayType = ctypes.c_ushort * num_samples
    packet.chan_1_vlt = SineWaveArrayType(*output)

    amplitude = 24000 / 2  # Max value for uint16 is 65535
    offset = amplitude  # Shift sine wave to positive range
    x = np.linspace(0, 6 * np.pi, num_samples, endpoint=False)
    sine_wave = np.sin(x)
    output = np.uint16((sine_wave * amplitude) + offset)
    SineWaveArrayType = ctypes.c_ushort * num_samples
    packet.chan_0_int = SineWaveArrayType(*output)

    amplitude = 5000 / 2  # Max value for uint16 is 65535
    offset = amplitude  # Shift sine wave to positive range
    x = np.linspace(0, 10 * np.pi, num_samples, endpoint=False)
    sine_wave = np.sin(x)
    output = np.uint16((sine_wave * amplitude) + offset)
    SineWaveArrayType = ctypes.c_ushort * num_samples
    packet.chan_1_int = SineWaveArrayType(*output)

    prepare_connect_and_run_mqtt_client()

if __name__ == "__main__":
    main()
