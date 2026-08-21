import os
import json
from pathlib import Path

# Paths
CONFIG_DIR = Path.home() / ".config" / "recorder-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
STORAGE_DIR = Path.home() / "Record"

# Default Settings
DEFAULT_CONFIG = {
    "max_duration_sec": 1800,  # 30 minutes
    "max_recordings": 5,
    "record_mic": True
}

def ensure_dirs():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_config() -> dict:
    ensure_dirs()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge with defaults in case of missing keys
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            return config
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
