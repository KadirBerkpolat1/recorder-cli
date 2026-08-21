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
    if [ "$(id -u)" != "0" ]; then SUDO="sudo"; else SUDO=""; fi
    $SUDO pacman -S --needed --noconfirm git python mpv
    if ! command_exists gpu-screen-recorder; then
        $SUDO pacman -S --needed --noconfirm gpu-screen-recorder || echo "WARNING: gpu-screen-recorder could not be installed automatically."
    fi
elif command_exists apt; then
    echo "Debian/Ubuntu detected. Installing missing dependencies..."
    if [ "$(id -u)" != "0" ]; then SUDO="sudo"; else SUDO=""; fi
    $SUDO apt update
    $SUDO apt install -y git python3 python3-venv mpv
elif command_exists dnf; then
    echo "Fedora detected. Installing missing dependencies..."
    if [ "$(id -u)" != "0" ]; then SUDO="sudo"; else SUDO=""; fi
    $SUDO dnf install -y git python3 mpv
elif command_exists zypper; then
    echo "openSUSE detected. Installing missing dependencies..."
    if [ "$(id -u)" != "0" ]; then SUDO="sudo"; else SUDO=""; fi
    $SUDO zypper install -y git python3 mpv
else
    echo "Unsupported package manager. Please ensure git, python, and mpv are installed manually."
fi

if ! command_exists gpu-screen-recorder; then
    echo ""
    echo "========================================================================="
    echo "WARNING: 'gpu-screen-recorder' is not installed or not in standard repos."
    echo "This tool is REQUIRED for recording."
    echo "Please install it manually from: https://git.dec05eba.com/gpu-screen-recorder/about/"
    echo "For Ubuntu/Fedora, you can usually install it via Flatpak or compile it."
    echo "========================================================================="
    echo ""
    sleep 3
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
