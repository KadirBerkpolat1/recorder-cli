#!/bin/bash
set -e

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
python3 -m venv venv
source venv/bin/activate

echo "Installing package..."
pip install -e .

echo "Creating 'recorder' command in $BIN_DIR..."
ln -sf "$INSTALL_DIR/venv/bin/recorder" "$BIN_DIR/recorder"

echo "========================================"
echo "Installation successful!"
echo "The command 'recorder' is now available."
echo ""
echo "Note: If you get a 'command not found' error, make sure"
echo "$BIN_DIR is added to your system PATH in your shell config (e.g. ~/.bashrc or ~/.zshrc)."
echo "========================================"
