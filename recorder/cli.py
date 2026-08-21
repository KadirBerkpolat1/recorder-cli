import argparse
import sys
import subprocess
from .config import ensure_dirs, load_config, save_config, STORAGE_DIR
from .recorder import ScreenRecorder
from .storage import list_recordings, delete_recording, clean_all
from . import __version__

def is_recording_active():
    try:
        subprocess.run(["pgrep", "-f", "gpu-screen-recorder"], stdout=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def cmd_daemon(args=None):
    ensure_dirs()
    recorder = ScreenRecorder()
    filepath = recorder.start()
    if not filepath:
        sys.exit(1)
    recorder.wait_and_stop()

def cmd_record(args=None):
    ensure_dirs()
    if is_recording_active():
        print("Recording is already running!")
        return

    print("Starting recording in the background...")
    subprocess.Popen(
        ["recorder", "daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    print("Recording started!")

def cmd_stop(args=None):
    try:
        subprocess.run(["pkill", "-2", "-f", "gpu-screen-recorder"], check=True)
        print("Stop signal sent to recorder.")
    except subprocess.CalledProcessError:
        print("No active recording found.")

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
        config = load_config()
        print("\n=== Settings ===")
        print(f"1. Max Duration: {config.get('max_duration_sec', 1800) // 60} minutes")
        print(f"2. Max Recordings: {config.get('max_recordings', 5)}")
        print(f"3. Record Microphone: {'Yes' if config.get('record_mic', True) else 'No'}")
        print("4. Back")
        
        choice = input("Select an option: ")
        
        if choice == '1':
            mins = input("Enter new max duration in minutes: ")
            if mins.isdigit():
                config['max_duration_sec'] = int(mins) * 60
                save_config(config)
        elif choice == '2':
            recs = input("Enter new max recordings limit: ")
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
        print("\n=== Videos ===")
        recs = cmd_list()
        if not recs:
            input("Press Enter to return...")
            break
            
        print("\nEnter a number to play the video, or 'd <number>' to delete (e.g., 'd 1').")
        print("Type 'q' to go back.")
        choice = input("Select: ").strip().lower()
        
        if choice == 'q':
            break
        elif choice.startswith('d '):
            idx = choice.split(' ')[1]
            if idx.isdigit():
                idx = int(idx)
                if 1 <= idx <= len(recs):
                    delete_recording(idx - 1)
                    print("Deleted.")
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(recs):
                filepath = STORAGE_DIR / recs[idx - 1].get_display_name()
                subprocess.Popen(["xdg-open", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Playing video...")

def interactive_menu():
    while True:
        is_active = is_recording_active()
        status = "🔴 Not Recording" if not is_active else "🟢 RECORDING"
        
        print("\n=== Recorder CLI ===")
        print(f"Status: {status}")
        print("1. Start Recording" if not is_active else "1. Stop Recording")
        print("2. Manage Videos")
        print("3. Settings")
        print("4. Exit")
        
        choice = input("Select an option: ")
        
        if choice == '1':
            if is_active:
                cmd_stop()
            else:
                cmd_record()
        elif choice == '2':
            interactive_videos()
        elif choice == '3':
            interactive_settings()
        elif choice == '4':
            print("Goodbye!")
            break

def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(description="Screen recording CLI tool")
    parser.add_argument("-v", "--version", action="version", version=f"recorder-cli {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    parser_record = subparsers.add_parser("record", help="Start recording")
    parser_record.set_defaults(func=cmd_record)

    parser_stop = subparsers.add_parser("stop", help="Stop current recording")
    parser_stop.set_defaults(func=cmd_stop)

    parser_list = subparsers.add_parser("list", help="List recordings")
    parser_list.set_defaults(func=cmd_list)

    parser_delete = subparsers.add_parser("delete", help="Delete a recording by index")
    parser_delete.add_argument("index", type=int, help="Index of the recording to delete (1=newest)")
    parser_delete.set_defaults(func=cmd_delete)

    parser_clean = subparsers.add_parser("clean", help="Delete all recordings")
    parser_clean.set_defaults(func=cmd_clean)

    parser_daemon = subparsers.add_parser("daemon")
    parser_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
