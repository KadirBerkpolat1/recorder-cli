import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional
from .config import STORAGE_DIR, MAX_RECORDINGS

@dataclass
class Recording:
    filepath: str
    start_time: str
    end_time: Optional[str] = None
    duration_sec: Optional[int] = None

    def get_display_name(self) -> str:
        return self.filepath.split("/")[-1]

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
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in recordings], f, indent=2)

def list_recordings() -> List[Recording]:
    recordings = _load_db()
    return sorted(recordings, key=lambda r: r.start_time, reverse=True)

def add_recording(filepath: str, start_time: str) -> Recording:
    recordings = list_recordings()
    rec = Recording(filepath=filepath, start_time=start_time)
    recordings.insert(0, rec)
    
    # Enforce max 5
    while len(recordings) > MAX_RECORDINGS:
        oldest = recordings.pop()
        old_file = STORAGE_DIR / oldest.filepath.split("/")[-1]
        if old_file.exists():
            old_file.unlink()
            
    _save_db(recordings)
    return rec

def update_recording(filepath: str, new_filepath: str, end_time: str, duration_sec: int):
    recordings = list_recordings()
    for rec in recordings:
        if rec.filepath == filepath:
            rec.filepath = new_filepath
            rec.end_time = end_time
            rec.duration_sec = duration_sec
            break
    _save_db(recordings)

def delete_recording(index: int) -> bool:
    recordings = list_recordings()
    if 0 <= index < len(recordings):
        rec = recordings.pop(index)
        file_path = STORAGE_DIR / rec.filepath.split("/")[-1]
        if file_path.exists():
            file_path.unlink()
        _save_db(recordings)
        return True
    return False

def clean_all() -> int:
    recordings = list_recordings()
    count = len(recordings)
    for rec in recordings:
        file_path = STORAGE_DIR / rec.filepath.split("/")[-1]
        if file_path.exists():
            file_path.unlink()
    _save_db([])
    return count
