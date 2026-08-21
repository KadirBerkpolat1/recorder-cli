import os
from pathlib import Path

MAX_DURATION = 1800  # 30 minutes in seconds
MAX_RECORDINGS = 5
STORAGE_DIR = Path.home() / "Record"

def ensure_storage_dir():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
