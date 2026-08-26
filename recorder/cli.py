import argparse
import sys
import subprocess
import time
import shutil
from pathlib import Path
from .config import ensure_dirs, load_config, save_config, STORAGE_DIR, CONFIG_DIR
from .recorder import ScreenRecorder, ContinuousRecorder
from .storage import list_recordings, delete_recording, clean_all
from . import __version__

SERVICE_NAME = "recorder.service"
USER_SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
USER_SERVICE_PATH = USER_SYSTEMD_DIR / SERVICE_NAME

def is_recording_active():
    try:
        subprocess.run(["pgrep", "-f", "gpu-screen-recorder"], stdout=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def is_service_active():
    try:
        res = subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME], check=False)
        return res.returncode == 0
    except Exception:
        return False

def is_service_enabled():
    try:
        res = subprocess.run(["systemctl", "--user", "is-enabled", "--quiet", SERVICE_NAME], check=False)
        return res.returncode == 0
    except Exception:
        return False

def install_systemd_service():
    """Install or update the systemd user service unit"""
    USER_SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    recorder_bin = shutil.which("recorder") or str(Path.home() / ".local" / "bin" / "recorder")
    
    unit_content = f"""[Unit]
Description=Recorder CLI - Continuous Circular Screen & Audio Recorder
Documentation=https://github.com/KadirBerkpolat1/recorder-cli
After=graphical-session.target pipewire.service
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart={recorder_bin} daemon
Restart=on-failure
RestartSec=3
KillSignal=SIGTERM
TimeoutStopSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target default.target
"""
    with open(USER_SERVICE_PATH, "w", encoding="utf-8") as f:
        f.write(unit_content)
    
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)

def cmd_daemon(args=None):
    """Runs continuous circular recording loop (ideal for systemd)"""
    ensure_dirs()
    continuous = ContinuousRecorder()
    continuous.run()

def cmd_record(args=None):
    ensure_dirs()
    if is_recording_active() or is_service_active():
        print("Recording is already running!")
        return

    # If systemd service is installed, prefer starting via systemd
    if USER_SERVICE_PATH.exists():
        print("Starting continuous recording via systemd service...")
        subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], check=False)
        time.sleep(0.5)
        if is_recording_active():
            print("✓ Recording started successfully.")
            return

    print("Starting continuous recording in background daemon...")
    subprocess.Popen(
        ["recorder", "daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    time.sleep(0.5)
    print("✓ Recording started.")

def cmd_stop(args=None):
    stopped_anything = False
    
    # 1. Stop systemd service if active
    if is_service_active():
        print("Stopping systemd recording service (saving current video)...")
        subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], check=False)
        stopped_anything = True

    # 2. If standalone daemon/gpu-screen-recorder is running, send SIGINT for graceful finalization
    if is_recording_active():
        try:
            subprocess.run(["pkill", "-2", "-f", "gpu-screen-recorder"], check=True)
            stopped_anything = True
        except subprocess.CalledProcessError:
            pass

    if stopped_anything:
        print("✓ Recording stopped and current video saved cleanly.")
    else:
        print("No active recording found.")

def cmd_service(args):
    action = args.action.lower()
    install_systemd_service()

    if action == "enable":
        subprocess.run(["systemctl", "--user", "enable", "--now", SERVICE_NAME], check=False)
        print("✓ Systemd servisi etkinleştirildi ve başlatıldı (Her oturum açılışında sürekli kayıt alacak).")
    elif action == "disable":
        subprocess.run(["systemctl", "--user", "disable", "--now", SERVICE_NAME], check=False)
        print("✓ Systemd servisi devre dışı bırakıldı ve durduruldu.")
    elif action == "start":
        subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], check=False)
        print("✓ Systemd servisi başlatıldı.")
    elif action == "stop":
        subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], check=False)
        print("✓ Systemd servisi durduruldu (O ana kadarki kayıt kaydedildi).")
    elif action == "status":
        active = is_service_active()
        enabled = is_service_enabled()
        rec_active = is_recording_active()
        print(f"Service Active   : {'🟢 YES' if active else '🔴 NO'}")
        print(f"Auto-start (Boot): {'🟢 ENABLED' if enabled else '⚪ DISABLED'}")
        print(f"Screen Recording : {'🟢 RECORDING' if rec_active else '🔴 IDLE'}")
    elif action == "install":
        print("✓ Systemd user unit installed and daemon reloaded.")

def cmd_list(args=None):
    recordings = list_recordings()
    if not recordings:
        print("No recordings found.")
        return recordings
        
    print(f"{'#':<3} | {'Date':<10} | {'Time Range':<11} | {'Duration':<8} | {'File'}")
    print("-" * 75)
    for i, rec in enumerate(recordings, 1):
        date_part = rec.start_time.split('_')[0] if '_' in rec.start_time else rec.start_time
        time_range = ""
        if '_' in rec.start_time:
            start_t = rec.start_time.split('_')[1].replace('-', ':')[:5]
            end_t = rec.end_time.replace('-', ':') if rec.end_time else "..."
            time_range = f"{start_t}-{end_t}"
            
        dur = f"{rec.duration_sec}s" if rec.duration_sec is not None else "..."
        print(f"{i:<3} | {date_part:<10} | {time_range:<11} | {dur:<8} | {rec.get_display_name()}")
    
    return recordings

def cmd_delete(args):
    if delete_recording(args.index - 1):
        print(f"Deleted recording #{args.index}.")
    else:
        print(f"Recording #{args.index} not found.")

def cmd_clean(args=None):
    ans = input("Are you sure you want to delete all recordings? [y/N] ")
    if ans.lower() == 'y':
        count = clean_all()
        print(f"Deleted {count} recordings.")
    else:
        print("Aborted.")

def interactive_settings():
    while True:
        print('\033c', end='')  # Clear screen
        config = load_config()
        print("=== Settings ===")
        print(f"1. Segment Duration  : {config.get('max_duration_sec', 1800) // 60} minutes")
        print(f"2. Max Saved Videos  : {config.get('max_recordings', 5)} files")
        print(f"3. Record Microphone : {'Yes' if config.get('record_mic', True) else 'No'}")
        print("4. Back")
        
        try:
            choice = input("\nSelect an option: ")
        except KeyboardInterrupt:
            return
            
        if choice == '1':
            try:
                mins = input("Enter new segment duration in minutes (e.g. 30): ")
            except KeyboardInterrupt:
                continue
            if mins.isdigit():
                config['max_duration_sec'] = int(mins) * 60
                save_config(config)
        elif choice == '2':
            try:
                recs = input("Enter max saved videos limit (circular buffer): ")
            except KeyboardInterrupt:
                continue
            if recs.isdigit():
                config['max_recordings'] = int(recs)
                save_config(config)
        elif choice == '3':
            config['record_mic'] = not config.get('record_mic', True)
            save_config(config)
        elif choice == '4':
            break

def interactive_videos():
    while True:
        print('\033c', end='')  # Clear screen
        print("=== Videos ===")
        recs = cmd_list()
        if not recs:
            try:
                input("\nPress Enter to return...")
            except KeyboardInterrupt:
                pass
            break
            
        print("\nEnter a number to play the video, or 'd <number>' to delete (e.g., 'd 1').")
        print("Type 'q' to go back.")
        
        try:
            choice = input("\nSelect: ").strip().lower()
        except KeyboardInterrupt:
            return
            
        if choice == 'q':
            break
        elif choice.startswith('d '):
            idx = choice.split(' ')[1]
            if idx.isdigit():
                idx = int(idx)
                if 1 <= idx <= len(recs):
                    delete_recording(idx - 1)
                    print("Deleted.")
                    time.sleep(0.5)
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(recs):
                filepath = STORAGE_DIR / recs[idx - 1].get_display_name()
                try:
                    subprocess.run(["which", "mpv"], stdout=subprocess.DEVNULL, check=True)
                    subprocess.Popen(["mpv", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except subprocess.CalledProcessError:
                    subprocess.Popen(["xdg-open", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Playing video...")
                time.sleep(0.5)

def interactive_menu():
    while True:
        print('\033c', end='')  # Clear screen
        is_rec = is_recording_active()
        is_svc = is_service_active()
        is_en = is_service_enabled()
        
        if is_svc:
            status = "🟢 RECORDING (Systemd Service Active)"
        elif is_rec:
            status = "🟢 RECORDING (Standalone Daemon Active)"
        else:
            status = "🔴 Not Recording"
            
        svc_auto = "🟢 Enabled (Autostart on Login)" if is_en else "⚪ Disabled"

        print("=== 🎥 Recorder CLI ===")
        print(f"Recording Status: {status}")
        print(f"Background Service: {svc_auto}")
        print("-" * 40)
        print("1. Stop Recording" if (is_rec or is_svc) else "1. Start Recording")
        print("2. Toggle Systemd Auto-Start Service (Enable/Disable)")
        print("3. Manage Videos")
        print("4. Settings")
        print("5. Exit")
        
        try:
            choice = input("\nSelect an option: ")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
            
        if choice == '1':
            if is_rec or is_svc:
                cmd_stop()
                time.sleep(0.5)
            else:
                cmd_record()
                time.sleep(0.5)
        elif choice == '2':
            if is_en:
                cmd_service(argparse.Namespace(action="disable"))
            else:
                cmd_service(argparse.Namespace(action="enable"))
            time.sleep(1)
        elif choice == '3':
            interactive_videos()
        elif choice == '4':
            interactive_settings()
        elif choice == '5':
            print("Goodbye!")
            break

def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(description="Screen & audio circular recording tool")
    parser.add_argument("-v", "--version", action="version", version=f"recorder-cli {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    parser_record = subparsers.add_parser("record", help="Start continuous recording")
    parser_record.set_defaults(func=cmd_record)

    parser_stop = subparsers.add_parser("stop", help="Stop current recording and save video")
    parser_stop.set_defaults(func=cmd_stop)

    parser_service = subparsers.add_parser("service", help="Manage systemd user service (enable, disable, start, stop, status)")
    parser_service.add_argument("action", choices=["enable", "disable", "start", "stop", "status", "install"], help="Service action")
    parser_service.set_defaults(func=cmd_service)

    parser_list = subparsers.add_parser("list", help="List recordings")
    parser_list.set_defaults(func=cmd_list)

    parser_delete = subparsers.add_parser("delete", help="Delete a recording by index")
    parser_delete.add_argument("index", type=int, help="Index of the recording to delete (1=newest)")
    parser_delete.set_defaults(func=cmd_delete)

    parser_clean = subparsers.add_parser("clean", help="Delete all recordings")
    parser_clean.set_defaults(func=cmd_clean)

    parser_daemon = subparsers.add_parser("daemon", help="Run recording loop in foreground")
    parser_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
