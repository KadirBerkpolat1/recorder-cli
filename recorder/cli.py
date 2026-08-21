import argparse
import sys
import subprocess
from .config import ensure_storage_dir
from .recorder import ScreenRecorder
from .storage import list_recordings, delete_recording, clean_all
from . import __version__

def cmd_daemon(args):
    ensure_storage_dir()
    recorder = ScreenRecorder()
    filepath = recorder.start()
    if not filepath:
        sys.exit(1)
    recorder.wait_and_stop()

def cmd_record(args):
    ensure_storage_dir()
    print("Starting recording in the background...")
    
    # Launch the daemon process detached from the current terminal
    subprocess.Popen(
        ["recorder", "daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    
    print("Recording started!")
    print("Run 'recorder list' to view it, or 'recorder stop' to end it.")
def cmd_stop(args):
    try:
        subprocess.run(["pkill", "-2", "-f", "gpu-screen-recorder"], check=True)
        print("Stop signal sent to recorder.")
    except subprocess.CalledProcessError:
        print("No active recording found.")

def cmd_list(args):
    recordings = list_recordings()
    if not recordings:
        print("No recordings found.")
        return
        
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

def cmd_delete(args):
    if delete_recording(args.index - 1):
        print(f"Deleted recording #{args.index}.")
    else:
        print(f"Recording #{args.index} not found.")

def cmd_clean(args):
    ans = input("Are you sure you want to delete all recordings? [y/N] ")
    if ans.lower() == 'y':
        count = clean_all()
        print(f"Deleted {count} recordings.")
    else:
        print("Aborted.")

def main():
    parser = argparse.ArgumentParser(description="Screen recording CLI tool")
    parser.add_argument("-v", "--version", action="version", version=f"recorder-cli {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    # record
    parser_record = subparsers.add_parser("record", help="Start recording")
    parser_record.set_defaults(func=cmd_record)

    # stop
    parser_stop = subparsers.add_parser("stop", help="Stop current recording")
    parser_stop.set_defaults(func=cmd_stop)

    # list
    parser_list = subparsers.add_parser("list", help="List recordings")
    parser_list.set_defaults(func=cmd_list)

    # delete
    parser_delete = subparsers.add_parser("delete", help="Delete a recording by index")
    parser_delete.add_argument("index", type=int, help="Index of the recording to delete (1=newest)")
    parser_delete.set_defaults(func=cmd_delete)

    # clean
    parser_clean = subparsers.add_parser("clean", help="Delete all recordings")
    parser_clean.set_defaults(func=cmd_clean)

    # daemon (hidden)
    parser_daemon = subparsers.add_parser("daemon")
    parser_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
