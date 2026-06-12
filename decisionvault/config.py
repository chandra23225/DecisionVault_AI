import os

from dotenv import load_dotenv


load_dotenv()


def get_config_value(name, default=None):
    return os.getenv(name, default)


def get_int_config_value(name, default):
    return int(get_config_value(name, str(default)))
