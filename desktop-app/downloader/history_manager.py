import json
import os
import time

HISTORY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "history.json")

MAX_HISTORY_ENTRIES = 500


def load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return []


def add_history_entry(filename, path, size_bytes, status, url="", category="Other"):
    history = load_history()
    entry = {
        "filename": filename,
        "path": path,
        "size_bytes": size_bytes,
        "status": status,
        "category": category,
        "url": url,
        "timestamp": time.time()
    }
    history.insert(0, entry)
    history = history[:MAX_HISTORY_ENTRIES]

    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def clear_history():
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump([], f)