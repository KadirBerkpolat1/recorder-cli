import subprocess
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from .config import STORAGE_DIR, ensure_dirs, load_config
from .storage import add_recording, update_recording

class ScreenRecorder:
    def __init__(self):
        self.process = None
        self.current_filepath = None
        self.start_time_dt = None

    def start(self):
        ensure_dirs()
        self.start_time_dt = datetime.now()
        start_str = self.start_time_dt.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{start_str}.mp4"
        self.current_filepath = str(STORAGE_DIR / filename)

        config = load_config()
        audio_arg = "default_output"
        if config.get("record_mic", True):
            audio_arg += "|default_input"

        cmd = [
            "gpu-screen-recorder",
            "-w", "screen",
            "-f", "60",
            "-a", audio_arg,
            "-o", self.current_filepath
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            add_recording(self.current_filepath, start_str)
            return self.current_filepath
        except FileNotFoundError:
            print("Error: gpu-screen-recorder is not installed. Please install it first.")
            return None

    def stop(self):
        """Send SIGINT to gpu-screen-recorder so it cleanly closes the MP4 container"""
        if self.process and self.process.poll() is None:
            try:
                self.process.send_signal(signal.SIGINT)
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception:
                pass

    def _finalize(self):
        """Rename completed file to include end timestamp and update database"""
        if not self.start_time_dt or not self.current_filepath:
            return None, 0

        end_time_dt = datetime.now()
        end_str = end_time_dt.strftime("%H-%M")
        start_str = self.start_time_dt.strftime("%Y-%m-%d_%H-%M-%S")
        
        duration = int((end_time_dt - self.start_time_dt).total_seconds())
        
        new_filename = f"{start_str}_{end_str}.mp4"
        new_filepath = str(STORAGE_DIR / new_filename)
        
        curr_path = Path(self.current_filepath)
        if curr_path.exists():
            # If the recording is very short (< 1s) and 0 bytes, remove it
            if curr_path.stat().st_size == 0 and duration < 2:
                try:
                    curr_path.unlink()
                except Exception:
                    pass
                return None, 0
            try:
                curr_path.rename(new_filepath)
            except Exception:
                new_filepath = self.current_filepath
            
        update_recording(self.current_filepath, new_filepath, end_str, duration)
        
        ret_path = new_filepath
        self.process = None
        self.current_filepath = None
        return ret_path, duration


class ContinuousRecorder:
    """Manages continuous circular loop recording (dashcam mode / systemd service)"""
    def __init__(self):
        self.running = True
        self.current_recorder = None

    def run(self):
        ensure_dirs()

        def handle_shutdown(signum, frame):
            self.running = False
            if self.current_recorder:
                self.current_recorder.stop()

        # Catch termination signals for graceful MP4 closing
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, handle_shutdown)

        while self.running:
            self.current_recorder = ScreenRecorder()
            filepath = self.current_recorder.start()
            if not filepath:
                print("Failed to start recorder process. Retrying in 5 seconds...")
                time.sleep(5)
                continue

            config = load_config()
            timeout = config.get("max_duration_sec", 1800)

            # Wait for segment duration or early shutdown signal
            try:
                self.current_recorder.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Segment full (e.g. 30 mins) -> gracefully stop and start next chunk
                self.current_recorder.stop()
            except (KeyboardInterrupt, Exception):
                self.running = False
                self.current_recorder.stop()

            # Finalize the finished segment
            self.current_recorder._finalize()
            self.current_recorder = None

            if not self.running:
                break

            # Brief pause before starting the next segment
            time.sleep(1)
