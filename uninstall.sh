#!/bin/bash
set -e

echo "=== Recorder CLI Uninstallation ==="

SERVICE_NAME="recorder.service"
INSTALL_DIR="$HOME/.local/share/recorder-cli"
BIN_FILE="$HOME/.local/bin/recorder"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/recorder-cli"
STORAGE_DIR="$HOME/Record"

# 1. Stop and disable systemd service if running
echo "Checking background systemd service..."
if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "Stopping $SERVICE_NAME..."
    systemctl --user stop "$SERVICE_NAME" || true
fi

if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "Disabling $SERVICE_NAME..."
    systemctl --user disable "$SERVICE_NAME" || true
fi

# 2. Terminate any stray background recording processes
echo "Stopping any running recorder processes..."
pkill -2 -f "gpu-screen-recorder" 2>/dev/null || true
pkill -f "recorder daemon" 2>/dev/null || true

# 3. Remove systemd user service file & symlinks
echo "Removing systemd user service unit..."
rm -f "$SYSTEMD_USER_DIR/$SERVICE_NAME"
rm -f "$SYSTEMD_USER_DIR/default.target.wants/$SERVICE_NAME"
rm -f "$SYSTEMD_USER_DIR/graphical-session.target.wants/$SERVICE_NAME"
systemctl --user daemon-reload 2>/dev/null || true

# 4. Remove binary symlink
if [ -L "$BIN_FILE" ] || [ -f "$BIN_FILE" ]; then
    echo "Removing $BIN_FILE..."
    rm -f "$BIN_FILE"
fi

# 5. Remove installation directory (venv and package)
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation files from $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
fi

# 6. Ask for configuration and recordings cleanup
echo ""
read -r -p "Do you want to delete the configuration directory ($CONFIG_DIR)? [y/N] " del_config
if [[ "$del_config" =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    echo "Configuration removed."
fi

read -r -p "Do you want to delete recorded videos ($STORAGE_DIR)? [y/N] " del_storage
if [[ "$del_storage" =~ ^[Yy]$ ]]; then
    rm -rf "$STORAGE_DIR"
    echo "Recordings directory removed."
else
    echo "Recorded videos preserved in $STORAGE_DIR."
fi

echo ""
echo "=== Uninstallation Complete! ==="
echo "Recorder CLI has been removed from your system."
