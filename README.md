# Recorder CLI

A simple and efficient command-line tool for screen recording on Wayland, capturing both video (screen) and audio (system + microphone) simultaneously. It acts as a wrapper around `gpu-screen-recorder`.

## Features
- Records screen at 60 FPS using hardware encoding (if supported).
- Simultaneously captures desktop audio and microphone input.
- Limits recordings to a maximum of 30 minutes.
- Stores up to 5 recordings in the `~/Record` directory (auto-deletes the oldest when exceeding the limit).
- Command-line interface to start, stop, list, delete, and clean recordings.

## Requirements
- Linux with a Wayland compositor.
- [`gpu-screen-recorder`](https://git.dec05eba.com/gpu-screen-recorder/about/) installed on your system.
- `python` 3.8+

## Installation

An installation script is provided to easily set up a virtual environment and make the `recorder` command globally available in your `PATH`.

```bash
git clone https://github.com/KadirBerkpolat1/recorder-cli.git
cd recorder-cli
./install.sh
```

## Usage

Once installed, you can use the `recorder` command from anywhere.

- **Start a recording:**
  ```bash
  recorder record
  ```
  *(Press `Ctrl+C` to stop, or run `recorder stop` in another terminal)*

- **Stop the current recording:**
  ```bash
  recorder stop
  ```

- **List all recordings:**
  ```bash
  recorder list
  ```

- **Delete a specific recording:**
  ```bash
  recorder delete 1  # Deletes the most recent recording
  ```

- **Delete all recordings:**
  ```bash
  recorder clean
  ```

Recordings are saved to `~/Record` in the format `YYYY-MM-DD_HH-MM-SS_HH-MM.mp4`.
