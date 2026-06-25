# mqtt_receiver.py
import paho.mqtt.client as mqtt
from instance import data_funkce
import classifier as clf
import struct
import traceback
from datetime import datetime
import numpy as np
import os
from collections import deque
from nastaveni import WAVE_SAMPLE_LEN, format_str, FORMAT_TELEMETRY_V1, FORMAT_TELEMETRY_V2, BUFFER_TIMEOUT_SECONDS
from time import sleep, monotonic
from app_logger import get_logger
from mqtt_log import log_event

_TELEMETRY_V1_SIZE = struct.calcsize(FORMAT_TELEMETRY_V1)
_TELEMETRY_SIZE = struct.calcsize(FORMAT_TELEMETRY_V2)  # V2

packet_buffers = {}  # Globální buffer pro zprávy
buffer_timestamps = {}  # kdy přišel první paket každého bufferu (monotonic)

# ── Live log posledních příchozích zpráv (max 50) ──
recent_messages = deque(maxlen=50)

# ── Poslední "UNIT ALIVE" heartbeat per zařízení ──
device_alive: dict[int, str] = {}  # device_id → ISO timestamp


def _log_message(topic: str, client_id: str, registered: bool, note: str = ""):
    recent_messages.appendleft({
        "time": datetime.now().strftime("%H:%M:%S"),
        "topic": topic,
        "client_id": client_id,
        "registered": registered,
        "note": note,
    })


_device_session: dict = {}  # device_id -> {"ts": int, "ts_str": str}
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
    """Ukládá neúplné packet buffery po vypršení timeoutu místo jejich zahazování."""
    now = monotonic()
    stale = [k for k, t in list(buffer_timestamps.items()) if (now - t) > BUFFER_TIMEOUT_SECONDS]
    for k in stale:
        device_id, session_ts = k
        buf = packet_buffers.get(k, {})
        n_received = len(buf)

        if n_received == 0:
            packet_buffers.pop(k, None)
            buffer_timestamps.pop(k, None)
            _device_session.pop(k, None)
            continue

        # Zjisti celkový počet paketů z posledního přijatého
        last_pkt_raw = buf[max(buf.keys())]
        try:
            tmp = struct.unpack(format_str, last_pkt_raw)
            total_expected = tmp[3]  # total_packet_nr
        except Exception:
            total_expected = "?"

        print(f"[MQTT] Timeout: ukládám neúplný buffer zařízení {device_id} ({n_received}/{total_expected} paketů)")

        try:
            # Seřaď dostupné pakety a spoj
            ordered = [buf[i] for i in sorted(buf.keys())]
            bin_data = b"".join(ordered)

            session = _device_session.get(k, {})
            ts_str = session.get("ts_str", datetime.now().isoformat())
            measured_at = session.get("measured_at")

            base_path = f"data_storage/{device_id}"
            os.makedirs(base_path, exist_ok=True)
            filename = f"{base_path}/{ts_str.replace(':', '-')}_incomplete.bin"
            with open(filename, "wb") as f:
                f.write(bin_data)

            message_id = data_funkce.uloz_zpravu(
                device_id, f"NRF/{device_id}/UP_STREAM",
                n_received, filename, measured_at,
                is_complete=False,
            )
            log_event("INCOMPLETE", dev=device_id, rcvd=n_received, expected=total_expected, msg_id=message_id)
            _log_message("cleanup", str(device_id), True,
                         f"nekompletní zpráva uložena ({n_received}/{total_expected} paketů)")
            print(f"[MQTT] Nekompletní zpráva uložena: {filename} (msg_id={message_id})")
        except Exception as e:
            get_logger().error("Ukládání nekompletní zprávy selhalo [device=%s]: %s", device_id, e)
            _log_message("cleanup", str(device_id), True, f"chyba ukládání neúplné zprávy: {e}")

        packet_buffers.pop(k, None)
        buffer_timestamps.pop(k, None)
        _device_session.pop(k, None)


def on_sys_message(client_id: str, topic: str, payload: bytes):
    """Zpracuje telemetrický SYS paket (NRF/+/UP_STREAM_SYS)."""
    device_id = data_funkce.registerovano(client_id)
    if not device_id:
        _log_message(topic, client_id, False, "zařízení není registrováno")
        return

    if payload == b"UNIT ALIVE":
        device_alive[device_id] = datetime.now().isoformat(timespec="seconds")
        _log_message(topic, client_id, True, "UNIT ALIVE")
        print(f"[MQTT SYS] {topic} | {client_id} | ✓ registrováno | UNIT ALIVE")
        return

    print(f"[MQTT SYS] {client_id}: payload {len(payload)} B (V1={_TELEMETRY_V1_SIZE}, V2={_TELEMETRY_SIZE})")

    if len(payload) >= _TELEMETRY_SIZE:
        # --- V2 ---
        try:
            d = struct.unpack(FORMAT_TELEMETRY_V2, payload[:_TELEMETRY_SIZE])
        except struct.error as e:
            _log_message(topic, client_id, True, f"SYS V2 chyba rozbalení: {e}")
            get_logger().error("SYS V2 rozbalení selhalo [%s / %s]: %s", topic, client_id, e)
            return
        # 0=header,1=ver_maj,2=ver_min,3=hw_maj,4=hw_min,5=sw_maj,6=sw_min,
        # 7=timestamp,8=reserve,9=pkt_cnt,10=batt_mv,11=temp*1000,12=hum*1000,
        # 13=pres*1000,14=IMEI,15=DEV_ID,16=train_cnt,17=pwr_cycle,
        # 18=uptime_min,19=last_pwr_ts,20=status_bits,21=rssi,22=rsrp,
        # 23=rsrq,24=snr,25=modem_word,26=gps_lat,27=gps_lon,28=gps_alt,29=CRC
        podminka = {
            "device_id":       device_id,
            "temperature":     round(d[11] / 1000.0, 2),
            "humidity":        round(d[12] / 1000.0, 2),
            "pressure":        round(d[13] / 1000.0, 1),
            "batt_mv":         d[10],
            "signal_strength": d[21],
            "uptime_minutes":  d[18],
            "train_counter":   data_funkce.dej_pocet_zprav_zarizeni(device_id),
        }
        ver = f"V2 ({d[1]}.{d[2]})"

    elif len(payload) >= _TELEMETRY_V1_SIZE:
        # --- V1 ---
        try:
            d = struct.unpack(FORMAT_TELEMETRY_V1, payload[:_TELEMETRY_V1_SIZE])
        except struct.error as e:
            _log_message(topic, client_id, True, f"SYS V1 chyba rozbalení: {e}")
            get_logger().error("SYS V1 rozbalení selhalo [%s / %s]: %s", topic, client_id, e)
            return
        # 0=header,1=ver_maj,2=ver_min,3=timestamp,4=reserve,5=pkt_cnt,
        # 6=batt_mv,7=temp*1000,8=hum*1000,9=pres*1000,10=IMEI,11=DEV_ID,
        # 12=train_cnt,13=pwr_cycle,14=uptime_min,15=last_pwr_ts,
        # 16=status_bits,17=rssi,18=rsrp,19=rsrq,20=snr,21=modem_word,
        # 22=gps_lat,23=gps_lon,24=gps_alt,25=CRC
        podminka = {
            "device_id":       device_id,
            "temperature":     round(d[7] / 1000.0, 2),
            "humidity":        round(d[8] / 1000.0, 2),
            "pressure":        round(d[9] / 1000.0, 1),
            "batt_mv":         d[6],
            "signal_strength": d[17],
            "uptime_minutes":  d[14],
            "train_counter":   data_funkce.dej_pocet_zprav_zarizeni(device_id),
        }
        ver = f"V1 ({d[1]}.{d[2]})"

    else:
        _log_message(topic, client_id, True,
                     f"SYS neznámý formát ({len(payload)} B, min V1={_TELEMETRY_V1_SIZE} B) — hex: {payload[:16].hex()}")
        return

    data_funkce.uloz_podmínky(podminka)
    _log_message(topic, client_id, True,
                 f"SYS {ver}: {podminka['temperature']}°C, {podminka['humidity']}%, "
                 f"{podminka['batt_mv']} mV, sig {podminka['signal_strength']} dBm")
    print(f"[MQTT SYS] {topic} ({ver}) → {podminka}")


def on_message(client, userdata, msg):
    global packet_buffers
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
        get_logger().error("Rozbalení datového paketu selhalo [%s]: %s", msg.topic, e)
        log_event("PARSE_ERR", client=client_id, topic=msg.topic, error=str(e))
        print(f"[MQTT] Chyba rozbalení paketu z {msg.topic}: {e}")
        return

    device_id = data_funkce.registerovano(client_id)
    if not device_id:
        _log_message(msg.topic, client_id, False, "zařízení není registrováno")
        log_event("REJECTED", client=client_id, topic=msg.topic)
        print(f"[MQTT] Neregistrované zařízení: {client_id} ({msg.topic})")
        return

    _log_message(msg.topic, client_id, True, pkt_info)
    print(f"[MQTT] {msg.topic} → {pkt_info}")

    device_ts = packet.timestamp if packet.timestamp > 0 else int(datetime.now().timestamp())
    key = (device_id, device_ts)

    if key not in packet_buffers:
        packet_buffers[key] = {}
        buffer_timestamps[key] = monotonic()
        _device_session[key] = {
            "ts_str": datetime.fromtimestamp(device_ts).isoformat(),
            "measured_at": datetime.fromtimestamp(device_ts).isoformat(timespec="seconds"),
        }
        print(f"[MQTT] Nová sezení pro {device_id}, device_ts={device_ts}")

    # Obnov timestamp — timeout měří rozestup mezi pakety, ne celkový čas přenosu
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
        ts_str = _device_session[key]["ts_str"]
        filename = f"{base_path}/{ts_str.replace(':', '-')}.bin"
        with open(filename, "wb") as f:
            f.write(bin_data)

        # zápis do databáze
        measured_at = _device_session[key]["measured_at"]
        message_id = data_funkce.uloz_zpravu(device_id, msg.topic, packet.total_packet_nr, filename, measured_at)

        log_event("COMPLETE", dev=device_id, pkts=packet.total_packet_nr, msg_id=message_id)
        print(f"Complete message saved to {filename}")

        # automatická klasifikace vlaku
        try:
            result = clf.classify_bin_file(filename)
            if message_id:
                data_funkce.uloz_klasifikaci(message_id, result)
            print(f"[MQTT] Klasifikace: {result['typ_vlaku']}, rychlost {result['rychlost_kmh']} km/h, poškození {result['poskozeni_podvozku']}")
        except Exception as e:
            get_logger().error("Klasifikace selhala [msg_id=%s, file=%s]:\n%s", message_id, filename, traceback.format_exc())
            log_event("CLASSIFY_ERR", dev=device_id, msg_id=message_id, error=str(e))
            print(f"[MQTT] Chyba klasifikace: {e}")

        # cleanup
        del packet_buffers[key]
        buffer_timestamps.pop(key, None)
        _device_session.pop(key, None)


    
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