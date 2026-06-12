import os

from dotenv import load_dotenv


load_dotenv()


def is_placeholder_config_value(value):
    if not value:
        return False

    normalized = str(value).strip().lower()
    placeholder_markers = {
        "",
        "your_gemini_api_key_here",
        "replace_me",
        "changeme",
        "todo",
        "placeholder",
        "<your-key>",
        "<api-key>",
    }

    return normalized in placeholder_markers or normalized.startswith("your_")


def get_config_value(name, default=None):
    value = os.getenv(name)

    if value is None:
        return default

    if is_placeholder_config_value(value):
        return default

    return value


def get_int_config_value(name, default):
    return int(get_config_value(name, str(default)))
