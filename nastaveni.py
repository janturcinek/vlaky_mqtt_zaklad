import os

WAVE_SAMPLE_LEN = 1024

#format_str = f'<HHHHIIH{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}H{WAVE_SAMPLE_LEN}HH'
format_str = f'<HHHHIIH{WAVE_SAMPLE_LEN}h{WAVE_SAMPLE_LEN}h{WAVE_SAMPLE_LEN}h{WAVE_SAMPLE_LEN}hH'

class DevelopmentConfig:
    SECRET_KEY = 'tajny_klic'
    DATABASE = os.path.join(os.getcwd(), 'instance', 'vlaky.db')
    DEBUG = True

