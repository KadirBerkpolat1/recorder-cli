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
