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
    "record_mic": True,
    "codec": "hevc",           # hevc (H.265), av1, h264
    "fps": 60,
    "quality": "very_high",    # ultra, very_high, high, medium
    "monitor": "screen",       # screen or specific monitor name e.g. DP-2
    "notifications": True
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

def send_notification(title: str, message: str, urgency: str = "normal"):
    """Send desktop notification via notify-send if available and enabled"""
    config = load_config()
    if not config.get("notifications", True):
        return
    try:
        import shutil
        import subprocess
        if shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", "-a", "Recorder CLI", "-u", urgency, "-i", "camera-video", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
    except Exception:
        pass

def bootstrap_environment() -> bool:
    """
    Ensure WAYLAND_DISPLAY and required graphical session variables are present.
    If running under systemd before environment sync, pulls from systemd user session
    or discovers active Wayland sockets.
    """
    import subprocess
    
    # If already set and not empty, we are good
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
        return True

    # Attempt to sync from systemd user environment
    try:
        res = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k in ["WAYLAND_DISPLAY", "DISPLAY", "XDG_RUNTIME_DIR", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE"]:
                        if v and k not in os.environ:
                            os.environ[k] = v
    except Exception:
        pass

    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
        return True

    # Fallback: scan for wayland socket in XDG_RUNTIME_DIR or /run/user/<uid>
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    if runtime_dir.exists():
        sockets = list(runtime_dir.glob("wayland-*"))
        # exclude lock files
        sockets = [s for s in sockets if not s.name.endswith(".lock")]
        if sockets:
            os.environ["WAYLAND_DISPLAY"] = sockets[0].name
            return True

    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
