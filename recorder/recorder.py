import subprocess
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from .config import (
    STORAGE_DIR,
    ensure_dirs,
    load_config,
    send_notification,
    bootstrap_environment,
)
from .storage import add_recording, update_recording, sync_recordings

class ScreenRecorder:
    def __init__(self):
        self.process = None
        self.current_filepath = None
        self.start_time_dt = None
        self.last_error = None

    def start(self):
        ensure_dirs()
        if not bootstrap_environment():
            self.last_error = "No Wayland or X11 graphical display environment found."
            print(f"[Recorder] Error: {self.last_error}", file=sys.stderr)
            return None

        self.start_time_dt = datetime.now()
        start_str = self.start_time_dt.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{start_str}.mp4"
        self.current_filepath = str(STORAGE_DIR / filename)

        config = load_config()
        monitor = config.get("monitor", "screen")
        fps = str(config.get("fps", 60))
        codec = config.get("codec", "hevc")
        quality = config.get("quality", "very_high")

        # Audio routing
        audio_args = []
        audio_mode = config.get("audio_mode")
        if audio_mode is None:
            # Backward compatibility with record_mic boolean
            record_mic = config.get("record_mic", True)
            audio_arg = "default_output|default_input" if record_mic else "default_output"
            audio_args = ["-a", audio_arg]
        elif audio_mode == "both":
            audio_args = ["-a", "default_output|default_input"]
        elif audio_mode == "desktop":
            audio_args = ["-a", "default_output"]
        elif audio_mode == "mic":
            audio_args = ["-a", "default_input"]
        elif audio_mode == "none":
            audio_args = []

        cmd = [
            "gpu-screen-recorder",
            "-w", monitor,
            "-f", fps,
            "-c", "mp4",
            "-k", codec,
            "-q", quality,
        ] + audio_args + ["-o", self.current_filepath]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        except FileNotFoundError:
            self.last_error = "gpu-screen-recorder executable not found in PATH."
            print(f"[Recorder] Error: {self.last_error}", file=sys.stderr)
            return None

        # Early exit check (give it 1.2s to detect immediate initialization crash)
        time.sleep(1.2)
        if self.process.poll() is not None:
            stderr_output = ""
            if self.process.stderr:
                try:
                    stderr_output = self.process.stderr.read().strip()
                except Exception:
                    pass
            self.last_error = f"Exited immediately (code {self.process.returncode}): {stderr_output}"
            print(f"[Recorder] Error: {self.last_error}", file=sys.stderr)
            
            # Clean up ghost file if created
            p = Path(self.current_filepath)
            if p.exists() and p.stat().st_size == 0:
                try:
                    p.unlink()
                except Exception:
                    pass
            self.process = None
            self.current_filepath = None
            return None

        # Successfully started and running
        add_recording(self.current_filepath, start_str)
        send_notification("Recording Started", f"Capturing {monitor} @ {fps}fps ({codec.upper()})")
        return self.current_filepath

    def stop(self):
        """Send SIGINT to gpu-screen-recorder so it cleanly closes the MP4 container"""
        if self.process and self.process.poll() is None:
            try:
                self.process.send_signal(signal.SIGINT)
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
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

        curr_path = Path(self.current_filepath)
        if not curr_path.exists() or curr_path.stat().st_size == 0 or duration < 2:
            # Recording failed or empty
            if curr_path.exists():
                try:
                    curr_path.unlink()
                except Exception:
                    pass
            sync_recordings()
            self.process = None
            self.current_filepath = None
            return None, 0

        new_filename = f"{start_str}_{end_str}.mp4"
        new_filepath = str(STORAGE_DIR / new_filename)

        try:
            curr_path.rename(new_filepath)
        except Exception:
            new_filepath = self.current_filepath
            new_filename = curr_path.name

        update_recording(self.current_filepath, new_filepath, end_str, duration)
        send_notification("Recording Saved", f"Saved {new_filename} ({duration}s)")

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

        backoff = 3
        while self.running:
            self.current_recorder = ScreenRecorder()
            filepath = self.current_recorder.start()
            
            if not filepath:
                print(f"[Recorder Loop] Failed to start recorder. Retrying in {backoff}s...", file=sys.stderr)
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)  # Exponential backoff up to 30s
                continue

            # Successful start -> reset backoff
            backoff = 3
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
