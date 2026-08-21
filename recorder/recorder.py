import subprocess
import os
import signal
import time
from datetime import datetime
from pathlib import Path
from .config import STORAGE_DIR, MAX_DURATION
from .storage import add_recording, update_recording

class ScreenRecorder:
    def __init__(self):
        self.process = None
        self.current_filepath = None
        self.start_time_dt = None

    def start(self):
        self.start_time_dt = datetime.now()
        start_str = self.start_time_dt.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{start_str}.mp4"
        self.current_filepath = str(STORAGE_DIR / filename)

        cmd = [
            "gpu-screen-recorder",
            "-w", "screen",
            "-f", "60",
            "-a", "default_output|default_input",
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
        except Exception as e:
            print(f"Failed to start recording: {e}")
            return None

    def wait_and_stop(self, timeout=MAX_DURATION):
        if not self.process:
            return None
            
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.stop()
        except KeyboardInterrupt:
            self.stop()
            
        return self._finalize()

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def _finalize(self):
        end_time_dt = datetime.now()
        end_str = end_time_dt.strftime("%H-%M")
        start_str = self.start_time_dt.strftime("%Y-%m-%d_%H-%M-%S")
        
        duration = int((end_time_dt - self.start_time_dt).total_seconds())
        
        new_filename = f"{start_str}_{end_str}.mp4"
        new_filepath = str(STORAGE_DIR / new_filename)
        
        if Path(self.current_filepath).exists():
            Path(self.current_filepath).rename(new_filepath)
            
        update_recording(self.current_filepath, new_filepath, end_str, duration)
        
        self.process = None
        return new_filepath, duration
