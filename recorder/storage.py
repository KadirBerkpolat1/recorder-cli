import os
import json
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .config import STORAGE_DIR, load_config

@dataclass
class Recording:
    filepath: str
    start_time: str
    end_time: Optional[str] = None
    duration_sec: Optional[int] = None
    file_size_bytes: Optional[int] = None

    def get_display_name(self) -> str:
        return Path(self.filepath).name

    def get_path(self) -> Path:
        # Handle relative or absolute paths correctly
        p = Path(self.filepath)
        if not p.is_absolute():
            p = STORAGE_DIR / p.name
        return p

    def exists(self) -> bool:
        p = self.get_path()
        return p.exists() and p.stat().st_size > 0

    def get_size_bytes(self) -> int:
        p = self.get_path()
        if p.exists():
            return p.stat().st_size
        return self.file_size_bytes or 0

    def get_formatted_size(self) -> str:
        bytes_val = self.get_size_bytes()
        if bytes_val <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} TB"
def _get_db_path() -> str:
    return str(STORAGE_DIR / "db.json")

def _load_db() -> List[Recording]:
    db_path = _get_db_path()
    if not (STORAGE_DIR / "db.json").exists():
        return []
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [Recording(**item) for item in data]
    except (json.JSONDecodeError, IOError):
        return []

def _save_db(recordings: List[Recording]):
    db_path = _get_db_path()
    data = [asdict(r) for r in recordings]
    # Atomic write via temporary file to prevent corruption
    dir_name = os.path.dirname(db_path)
    try:
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, db_path)
    except Exception:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
def sync_recordings() -> List[Recording]:
    """
    Synchronize db.json with files actually present on disk.
    Removes ghost recordings (files that don't exist or are 0-byte corrupt files).
    """
    recordings = _load_db()
    valid: List[Recording] = []
    changed = False
    
    for rec in recordings:
        p = rec.get_path()
        # Keep if file physically exists and is not 0 bytes, or if it has no end_time yet (currently recording)
        if p.exists() and p.stat().st_size > 0:
            rec.file_size_bytes = p.stat().st_size
            valid.append(rec)
        elif rec.end_time is None and p.exists():
            # In progress recording
            valid.append(rec)
        else:
            # File is missing or 0 bytes after completion -> ghost record
            changed = True
            if p.exists() and p.stat().st_size == 0:
                try:
                    p.unlink()
                except Exception:
                    pass

    if changed:
        _save_db(valid)
    return sorted(valid, key=lambda r: r.start_time, reverse=True)

def list_recordings(sync: bool = True) -> List[Recording]:
    if sync:
        return sync_recordings()
    recordings = _load_db()
    return sorted(recordings, key=lambda r: r.start_time, reverse=True)
def add_recording(filepath: str, start_time: str) -> Recording:
    recordings = list_recordings()
    rec = Recording(filepath=filepath, start_time=start_time)
    recordings.insert(0, rec)
    
    config = load_config()
    max_recs = config.get("max_recordings", 5)
    while len(recordings) > max_recs:
        oldest = recordings.pop()
        old_file = oldest.get_path()
        if old_file.exists():
            try:
                old_file.unlink()
            except Exception:
                pass
    _save_db(recordings)
    return rec

def update_recording(filepath: str, new_filepath: str, end_time: str, duration_sec: int):
    recordings = _load_db()
    for rec in recordings:
        if rec.filepath == filepath or rec.get_path() == Path(filepath):
            rec.filepath = new_filepath
            rec.end_time = end_time
            rec.duration_sec = duration_sec
            p = Path(new_filepath)
            if p.exists():
                rec.file_size_bytes = p.stat().st_size
            break
    _save_db(recordings)
    sync_recordings()

def delete_recording(index: int) -> bool:
    recordings = list_recordings()
    if 0 <= index < len(recordings):
        rec = recordings.pop(index)
        file_path = rec.get_path()
        if file_path.exists():
            file_path.unlink()
        _save_db(recordings)
        return True
    return False

def clean_all() -> int:
    recordings = list_recordings()
    count = len(recordings)
    for rec in recordings:
        file_path = rec.get_path()
        if file_path.exists():
            file_path.unlink()
    _save_db([])
    return count
