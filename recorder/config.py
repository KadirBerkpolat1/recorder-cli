import os
import json
from pathlib import Path

# Paths
CONFIG_DIR = Path.home() / ".config" / "recorder-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
STORAGE_DIR = Path.home() / "Record"

# Quality & Performance Presets
PRESETS = {
    "performance": {
        "name": "⚡ Performans",
        "desc": "1080p 30 FPS, Medium NVENC (Düşük donanım / laptop / sıfır kasma)",
        "resolution": "1080p",
        "fps": 30,
        "quality": "medium",
        "codec": "hevc",
    },
    "balanced": {
        "name": "⚖️ Dengeli",
        "desc": "1080p 60 FPS, High NVENC (Akıcı ve dengeli standart oyun kaydı)",
        "resolution": "1080p",
        "fps": 60,
        "quality": "high",
        "codec": "hevc",
    },
    "quality": {
        "name": "🎬 Yüksek Kalite",
        "desc": "1440p (2K) 60 FPS, Very High (Güçlü sistemler için)",
        "resolution": "1440p",
        "fps": 60,
        "quality": "very_high",
        "codec": "hevc",
    },
    "ultra": {
        "name": "💎 Ultra (Native)",
        "desc": "Orijinal Ekran Çözünürlüğü, 60 FPS, Ultra Kalite",
        "resolution": "native",
        "fps": 60,
        "quality": "ultra",
        "codec": "hevc",
    },
    "esports": {
        "name": "🚀 Espor / Yüksek Akıcılık",
        "desc": "1080p 120 FPS, High (Hızlı FPS oyunları için)",
        "resolution": "1080p",
        "fps": 120,
        "quality": "high",
        "codec": "hevc",
    },
}

def detect_aspect_ratio() -> str:
    """Detect current screen aspect ratio from Hyprland or system commands"""
    import subprocess
    import re
    try:
        out = subprocess.check_output(["hyprctl", "monitors"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.search(r"(\d{3,5})x(\d{3,5})@", line)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                ratio = w / h
                if abs(ratio - (16 / 10)) < 0.05:
                    return "16:10"
                elif abs(ratio - (16 / 9)) < 0.05:
                    return "16:9"
                elif abs(ratio - (21 / 9)) < 0.05:
                    return "21:9"
    except Exception:
        pass
    return "16:9"

def resolve_resolution(res_val) -> str | None:
    """
    Resolve friendly names (1080p, 1440p, 4k, 720p, native) to explicit WxH format.
    Accounts for 16:10 vs 16:9 aspect ratios automatically to prevent video stretching.
    """
    if not res_val:
        return None
    val = str(res_val).strip().lower()
    if val in ["none", "native", "original", "ekran", "0"]:
        return None
    if "x" in val:
        parts = val.split("x")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{parts[0]}x{parts[1]}"

    aspect = detect_aspect_ratio()
    is_16_10 = (aspect == "16:10")

    if val in ["1080p", "fhd", "1080"]:
        return "1920x1200" if is_16_10 else "1920x1080"
    elif val in ["1440p", "2k", "qhd"]:
        return "2560x1600" if is_16_10 else "2560x1440"
    elif val in ["4k", "2160p", "uhd"]:
        return "3840x2400" if is_16_10 else "3840x2160"
    elif val in ["720p", "hd"]:
        return "1280x800" if is_16_10 else "1280x720"
    return None

# Default Settings
DEFAULT_CONFIG = {
    "max_duration_sec": 1800,  # 30 minutes
    "max_recordings": 5,
    "record_mic": True,
    "codec": "hevc",           # hevc (H.265), av1, h264
    "fps": 60,
    "quality": "very_high",    # ultra, very_high, high, medium
    "resolution": "native",    # native, 4k, 1440p (2k), 1080p, 720p or WxH
    "preset": "custom",        # performance, balanced, quality, ultra, esports, custom
    "monitor": "screen",       # screen or specific monitor name e.g. DP-2
    "notifications": True
}

def apply_preset(preset_key: str) -> bool:
    key = preset_key.lower().strip()
    if key not in PRESETS:
        return False
    p = PRESETS[key]
    cfg = load_config()
    cfg["preset"] = key
    cfg["resolution"] = p["resolution"]
    cfg["fps"] = p["fps"]
    cfg["quality"] = p["quality"]
    cfg["codec"] = p["codec"]
    save_config(cfg)
    return True

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
