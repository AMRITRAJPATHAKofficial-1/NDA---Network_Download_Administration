import json
import os

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    "save_folder": os.path.join(os.path.expanduser("~"), "Downloads", "MyDownloader"),
    "num_connections": 8,
    "speed_limit_kbps": 0,              # 0 = unlimited
    "auto_start_enabled": False,
    "clipboard_monitoring_enabled": False
}


def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)