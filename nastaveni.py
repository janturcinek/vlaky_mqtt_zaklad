import os

APP_VERSION = "1.8"

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

