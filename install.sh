#!/bin/bash
set -e

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Check and install system dependencies if missing
MISSING_DEPS=()
if ! command_exists gpu-screen-recorder; then MISSING_DEPS+=("gpu-screen-recorder"); fi
if ! command_exists mpv; then MISSING_DEPS+=("mpv"); fi
if ! command_exists notify-send; then MISSING_DEPS+=("libnotify"); fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "Checking system dependencies: missing (${MISSING_DEPS[*]} metabundles)..."
    if [ "$(id -u)" != "0" ]; then SUDO="sudo"; else SUDO=""; fi
    
    if command_exists pacman; then
        echo "Installing missing dependencies via pacman..."
        $SUDO pacman -S --needed --noconfirm "${MISSING_DEPS[@]}" || true
    elif command_exists apt; then
        echo "Installing missing dependencies via apt..."
        $SUDO apt update && $SUDO apt install -y mpv libnotify-bin || true
    elif command_exists dnf; then
        echo "Installing missing dependencies via dnf..."
        $SUDO dnf install -y mpv libnotify || true
    elif command_exists zypper; then
        echo "Installing missing dependencies via zypper..."
        $SUDO zypper install -y mpv libnotify || true
    fi
fi

echo "Starting Recorder CLI installation..."

INSTALL_DIR="$HOME/.local/share/recorder-cli"
BIN_DIR="$HOME/.local/bin"

# Ensure ~/.local/bin exists
mkdir -p "$BIN_DIR"

echo "Copying files to $INSTALL_DIR..."
# Remove old install if exists
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR/"

echo "Setting up Python virtual environment..."
cd "$INSTALL_DIR"
# Remove any copied venv from source directory just in case
rm -rf venv

if command -v uv >/dev/null 2>&1; then
    echo "Using uv for fast virtual environment & dependency management..."
    uv venv venv
    source venv/bin/activate
    uv pip install -e .
else
    echo "uv not found, falling back to python3 venv and pip..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
fi
echo "Creating 'recorder' command in $BIN_DIR..."
ln -sf "$INSTALL_DIR/venv/bin/recorder" "$BIN_DIR/recorder"

echo "Registering systemd user service unit..."
"$INSTALL_DIR/venv/bin/recorder" service install >/dev/null 2>&1 || true

echo "========================================"
echo "Installation successful!"
echo "The command 'recorder' is now available."

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "WARNING: $BIN_DIR is not in your PATH."
    echo "Attempting to add it to ~/.bashrc and ~/.zshrc..."
    
    for shell_rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [ -f "$shell_rc" ]; then
            if ! grep -q "export PATH=.*$BIN_DIR" "$shell_rc"; then
                echo "export PATH=\"\$PATH:$BIN_DIR\"" >> "$shell_rc"
                echo "Added to $shell_rc"
            fi
        fi
    done
    
    echo "Please restart your terminal or run:"
    echo "  export PATH=\"\$PATH:$BIN_DIR\""
fi

echo "========================================"
