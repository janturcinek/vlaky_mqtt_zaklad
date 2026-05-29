# mqtt_receiver.py
import paho.mqtt.client as mqtt
from instance import data_funkce
import classifier as clf
import struct
from datetime import datetime
import numpy as np
import os
from collections import deque
from nastaveni import WAVE_SAMPLE_LEN, format_str, FORMAT_TELEMETRY_V2
from time import sleep, monotonic

_TELEMETRY_SIZE = struct.calcsize(FORMAT_TELEMETRY_V2)

packet_buffers = {}  # Globální buffer pro zprávy
buffer_timestamps = {}  # kdy přišel první paket každého bufferu (monotonic)
BUFFER_TIMEOUT_SECONDS = 30  # neúplné buffery starší než X sekund jsou zahozeny

# ── Live log posledních příchozích zpráv (max 50) ──
recent_messages = deque(maxlen=50)


def _log_message(topic: str, client_id: str, registered: bool, note: str = ""):
    recent_messages.appendleft({
        "time": datetime.now().strftime("%H:%M:%S"),
        "topic": topic,
        "client_id": client_id,
        "registered": registered,
        "note": note,
    })


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
        

def _cleanup_stale_buffers():
    """Zahazuje neúplné packet buffery starší než BUFFER_TIMEOUT_SECONDS."""
    now = monotonic()
    stale = [k for k, t in list(buffer_timestamps.items()) if (now - t) > BUFFER_TIMEOUT_SECONDS]
    for k in stale:
        n = len(packet_buffers.get(k, {}))
        print(f"[MQTT] Timeout: zahazuji neúplný buffer zařízení {k[0]} ({n} paketů)")
        _log_message("cleanup", str(k[0]), True, f"zahozena neúplná zpráva ({n} paketů, timeout {BUFFER_TIMEOUT_SECONDS}s)")
        packet_buffers.pop(k, None)
        buffer_timestamps.pop(k, None)


def on_sys_message(client_id: str, topic: str, payload: bytes):
    """Zpracuje telemetrický SYS paket (NRF/+/UP_STREAM_SYS)."""
    device_id = data_funkce.registerovano(client_id)
    if not device_id:
        _log_message(topic, client_id, False, "zařízení není registrováno")
        return

    if len(payload) < _TELEMETRY_SIZE:
        _log_message(topic, client_id, True, f"SYS paket příliš krátký ({len(payload)} B)")
        return

    try:
        d = struct.unpack(FORMAT_TELEMETRY_V2, payload[:_TELEMETRY_SIZE])
    except struct.error as e:
        _log_message(topic, client_id, True, f"SYS chyba rozbalení: {e}")
        return

    # d indexy dle FORMAT_TELEMETRY_V2:
    # 0=header,1=ver_maj,2=ver_min,3=hw_maj,4=hw_min,5=sw_maj,6=sw_min,
    # 7=timestamp,8=reserve,9=pkt_cnt,10=batt_mv,11=temp*1000,12=hum*1000,
    # 13=pres*1000,14=IMEI,15=DEV_ID,16=train_cnt,17=pwr_cycle,
    # 18=uptime_min,19=last_pwr_ts,20=status_bits,21=rssi,22=rsrp,
    # 23=rsrq,24=snr,25=modem_word,26=gps_lat,27=gps_lon,28=gps_alt,29=CRC
    podminka = {
        "device_id":      device_id,
        "temperature":    round(d[11] / 1000.0, 2),
        "humidity":       round(d[12] / 1000.0, 2),
        "pressure":       round(d[13] / 1000.0, 1),
        "batt_mv":        d[10],
        "signal_strength": d[21],
        "uptime_minutes": d[18],
        "train_counter":  data_funkce.dej_pocet_zprav_zarizeni(device_id),
    }
    data_funkce.uloz_podmínky(podminka)
    _log_message(topic, client_id, True,
                 f"SYS: {podminka['temperature']}°C, {podminka['humidity']}%, "
                 f"{podminka['batt_mv']} mV, sig {podminka['signal_strength']} dBm")
    print(f"[MQTT SYS] {topic} → {podminka}")


def on_message(client, userdata, msg):
    global packet_buffers
    global updated_workaround_timestamp
    global packet_timestamp_workaround
    global timestamp_str
    global on_msg_call_cntr

    on_msg_call_cntr += 1
    client_id = msg.topic.split('/')[1] if '/' in msg.topic else "unknown"
    topic_type = msg.topic.split('/')[-1] if '/' in msg.topic else ""

    # ── Cleanup starých bufferů ──
    _cleanup_stale_buffers()

    # ── SYS telemetrie ──
    if topic_type == "UP_STREAM_SYS":
        on_sys_message(client_id, msg.topic, msg.payload)
        return

    # Pokus o rozbalení paketu
    try:
        unpacked_data = struct.unpack(format_str, msg.payload)
        packet = DataPacket(unpacked_data)
        pkt_info = f"paket {packet.actual_packet_nr}/{packet.total_packet_nr}"
    except struct.error as e:
        _log_message(msg.topic, client_id, False, f"chyba rozbalení: {e}")
        print(f"[MQTT] Chyba rozbalení paketu z {msg.topic}: {e}")
        return

    device_id = data_funkce.registerovano(client_id)
    if not device_id:
        _log_message(msg.topic, client_id, False, "zařízení není registrováno")
        print(f"[MQTT] Neregistrované zařízení: {client_id} ({msg.topic})")
        return

    _log_message(msg.topic, client_id, True, pkt_info)
    print(f"[MQTT] {msg.topic} → {pkt_info}")

    if updated_workaround_timestamp == 1:
        packet_timestamp_workaround=int(datetime.now().timestamp())
        print(f"generating timestamp from local pc -> {packet_timestamp_workaround}")
        timestamp_str = datetime.fromtimestamp(packet_timestamp_workaround).isoformat()
        updated_workaround_timestamp=0

    key = (device_id, packet_timestamp_workaround)
    #key = (device_id, packet.timestamp)
    
    # 📦 místo listu použij slovník s číslem paketu jako klíč
    if key not in packet_buffers:
        packet_buffers[key] = {}
        buffer_timestamps[key] = monotonic()

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
        message_id = data_funkce.uloz_zpravu(device_id, msg.topic, packet.total_packet_nr, filename)

        print(f"Complete message saved to {filename}")

        # automatická klasifikace vlaku
        try:
            result = clf.classify_bin_file(filename)
            if message_id:
                data_funkce.uloz_klasifikaci(message_id, result)
            print(f"[MQTT] Klasifikace: {result['typ_vlaku']}, rychlost {result['rychlost_kmh']} km/h, poškození {result['poskozeni_podvozku']}")
        except Exception as e:
            print(f"[MQTT] Chyba klasifikace: {e}")

        # cleanup
        updated_workaround_timestamp=1
        print("enable future timestamp workaroud update")
        del packet_buffers[key]
        buffer_timestamps.pop(key, None)


    
def run_mqtt_receiver():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "FastAPI_MQTT_Receiver")
    client.username_pw_set("iot-course-but", "thisisthemostsecretsecretever")
    client.on_message = on_message

    def on_connect(c, u, f, rc):
        if rc == 0:
            print("[MQTT] Připojen k brokeru")
            c.subscribe("NRF/+/UP_STREAM")
            c.subscribe("NRF/+/UP_STREAM_SYS")
            print("[MQTT] Subscribed: NRF/+/UP_STREAM, NRF/+/UP_STREAM_SYS")
        else:
            print(f"[MQTT] Chyba připojení: {rc}")

    client.on_connect = on_connect
    client.connect("iot-course-but.cloud.shiftr.io", 1883)
    client.loop_forever()