import os

APP_VERSION = "2.8"

BUFFER_TIMEOUT_SECONDS = 30  # max. rozestup mezi pakety jednoho přenosu (s)

WAVE_SAMPLE_LEN = 1024

#format_str = f'<HHHHIIH{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}HH'
format_str = f'<HHHHIIH{WAVE_SAMPLE_LEN}h{WAVE_SAMPLE_LEN}h{WAVE_SAMPLE_LEN}h{WAVE_SAMPLE_LEN}hH'

# Formát telemetrického SYS paketu — V1 (bez hw/sw verze)
FORMAT_TELEMETRY_V1 = (
    "<"   # little-endian
    "H"   # packet_header
    "B"   # packet_ver_major
    "B"   # packet_ver_minor
    "I"   # timestamp
    "H"   # reserve_word
    "H"   # packet_counter
    "H"   # batt_voltage        (mV)
    "i"   # unit_temperature    (°C * 1000)
    "I"   # unit_humidity       (% * 1000)
    "I"   # unit_pressure       (Pa * 1000)
    "I"   # IMEI
    "I"   # DEV_ID
    "H"   # train_counter
    "H"   # pwr_cycle_counter
    "I"   # uptime_minutes
    "I"   # last_powercycle_timestamp
    "H"   # unit_status_bits
    "h"   # signal_strength     (dBm)
    "h"   # signal_rsrp
    "h"   # signal_rsrq
    "h"   # signal_snr
    "H"   # modem_status_word
    "f"   # GPS_lat
    "f"   # GPS_lon
    "f"   # GPS_alt
    "H"   # CRC
)

# Formát telemetrického SYS paketu — V2 (přidány hw_ver + sw_ver)
FORMAT_TELEMETRY_V2 = (
    "<"   # little-endian
    "H"   # packet_header
    "B"   # packet_ver_major
    "B"   # packet_ver_minor
    "B"   # hw_ver_major
    "B"   # hw_ver_minor
    "B"   # sw_ver_major
    "B"   # sw_ver_minor
    "I"   # timestamp
    "H"   # reserve_word
    "H"   # packet_counter
    "H"   # batt_voltage        (mV)
    "i"   # unit_temperature    (°C * 1000)
    "I"   # unit_humidity       (% * 1000)
    "I"   # unit_pressure       (Pa * 1000)
    "I"   # IMEI
    "I"   # DEV_ID
    "H"   # train_counter
    "H"   # pwr_cycle_counter
    "I"   # uptime_minutes
    "I"   # last_powercycle_timestamp
    "H"   # unit_status_bits
    "h"   # signal_strength     (dBm)
    "h"   # signal_rsrp
    "h"   # signal_rsrq
    "h"   # signal_snr
    "H"   # modem_status_word
    "f"   # GPS_lat
    "f"   # GPS_lon
    "f"   # GPS_alt
    "H"   # CRC
)

class DevelopmentConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tajny_klic_zmente_v_produkci')
    DATABASE = os.environ.get(
        'DATABASE_PATH',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'vlaky.db')
    )
    DEBUG = True

    # MQTT broker — výchozí hodnoty odpovídají sdílenému kurzovnímu brokeru;
    # lze přepsat proměnnými prostředí bez zásahu do kódu.
    MQTT_HOST = os.environ.get('MQTT_HOST', 'iot-course-but.cloud.shiftr.io')
    MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
    MQTT_USERNAME = os.environ.get('MQTT_USERNAME', 'iot-course-but')
    MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD', 'thisisthemostsecretsecretever')


# Výchozí databáze typů lokomotiv/vlaků pro klasifikaci (classifier.py).
# Jediný zdroj pravdy pro tato data — používá je jak počáteční seed tabulky
# train_types (instance/data_funkce.py::init_db), tak záložní fallback
# klasifikátoru pro případ, že SQLite není dostupné (classifier.py).
TRAIN_TYPES_SEED = [
    {"typ": "CZLoko1",             "pomer": 1.791667, "dvojkoli_mm": 2400, "popis": ""},
    {"typ": "CZLoko2",             "pomer": 2.75,     "dvojkoli_mm": 2400, "popis": ""},
    {"typ": "Škoda 380",           "pomer": 2.48,     "dvojkoli_mm": 2500, "popis": ""},
    {"typ": "ALSTOM TRAXX 160",    "pomer": 2.988462, "dvojkoli_mm": 2600, "popis": ""},
    {"typ": "ALSTOM TRAXX 160B",   "pomer": 2.996154, "dvojkoli_mm": 2600, "popis": ""},
    {"typ": "ALSTOM TRAXX 140",    "pomer": 3.015385, "dvojkoli_mm": 2600, "popis": ""},
    {"typ": "SIEMENS Vectron Dual","pomer": 3.0,      "dvojkoli_mm": 2700, "popis": ""},
    {"typ": "SIEMENS Vectron CD",  "pomer": 2.166667, "dvojkoli_mm": 3000, "popis": ""},
    {"typ": "SIEMENS Vectron",     "pomer": 2.3,      "dvojkoli_mm": 3000, "popis": ""},
    {"typ": "Škoda 363",           "pomer": 1.59375,  "dvojkoli_mm": 3200, "popis": ""},
    {"typ": "Pendolino",           "pomer": 6.037037, "dvojkoli_mm": 2700, "popis": "Jednotka ETR 470"},
    {"typ": "LEO Express",         "pomer": 4.925926, "dvojkoli_mm": 2700, "popis": ""},
    {"typ": "Panter",              "pomer": 6.916667, "dvojkoli_mm": 2400, "popis": ""},
    {"typ": "Elefant",             "pomer": 6.3,      "dvojkoli_mm": 2600, "popis": ""},
    {"typ": "Newag Dragon 2",      "pomer": 1.00,     "dvojkoli_mm": 1950, "popis": ""},
]

