import os

class DevelopmentConfig:
    SECRET_KEY = 'tajny_klic'
    DATABASE = os.path.join(os.getcwd(), 'instance', 'vlaky.db')
    DEBUG = True

