#!/bin/bash
set -e

echo "=== Recorder CLI Automated Setup ==="

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install dependencies based on OS
echo "Checking system dependencies..."
if command_exists pacman; then
    echo "Arch Linux detected. Installing missing dependencies..."
    # Only sudo if we are not root
    if [ "$(id -u)" != "0" ]; then
        SUDO="sudo"
    else
        SUDO=""
    fi
    $SUDO pacman -S --needed --noconfirm git python mpv gpu-screen-recorder
elif command_exists apt; then
    echo "Debian/Ubuntu detected. Installing missing dependencies..."
    if [ "$(id -u)" != "0" ]; then
        SUDO="sudo"
    else
        SUDO=""
    fi
    $SUDO apt update
    $SUDO apt install -y git python3 python3-venv mpv
    
    if ! command_exists gpu-screen-recorder; then
        echo "WARNING: gpu-screen-recorder not found in apt. Please install it manually for Debian/Ubuntu."
    fi
else
    echo "Unsupported package manager. Please ensure git, python, mpv, and gpu-screen-recorder are installed."
fi

# Clone repository to a temporary location
TMP_DIR=$(mktemp -d -t recorder-cli-XXXXXX)
echo "Cloning repository to $TMP_DIR..."
git clone https://github.com/KadirBerkpolat1/recorder-cli.git "$TMP_DIR"

# Run the project's install.sh
echo "Running installation script..."
cd "$TMP_DIR"
chmod +x install.sh
./install.sh

# Cleanup
echo "Cleaning up temporary files..."
cd "$HOME"
rm -rf "$TMP_DIR"

echo "=== Setup Complete! ==="
echo "You can now run 'recorder' from your terminal."
