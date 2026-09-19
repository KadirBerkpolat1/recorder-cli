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

echo ""
echo "Configuring PATH for all shells..."

# 1. Fish shell support (default interactive shell on CachyOS)
if command_exists fish; then
    fish -c "fish_add_path -U '$BIN_DIR'" 2>/dev/null || true
    echo "✓ Added to Fish universal PATH (instantly active)."
fi

# 2. Bash, Zsh and POSIX shell profiles
for shell_rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.bash_profile"; do
    if [ -f "$shell_rc" ]; then
        if ! grep -q "export PATH=.*$BIN_DIR" "$shell_rc"; then
            echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$shell_rc"
            echo "✓ Added to $shell_rc"
        fi
    fi
done

# 3. Global symlink to /usr/local/bin (universally in PATH for all shells without terminal restart)
if [ -w /usr/local/bin ]; then
    ln -sf "$BIN_DIR/recorder" /usr/local/bin/recorder 2>/dev/null && echo "✓ Created global symlink in /usr/local/bin/recorder"
elif command_exists sudo; then
    if [ "$(id -u)" = "0" ]; then
        ln -sf "$BIN_DIR/recorder" /usr/local/bin/recorder 2>/dev/null || true
    else
        sudo ln -sf "$BIN_DIR/recorder" /usr/local/bin/recorder 2>/dev/null && echo "✓ Created global symlink in /usr/local/bin/recorder (via sudo)" || true
    fi
fi

if [[ ":$PATH:" != *":$BIN_DIR:"* ]] && [ ! -f /usr/local/bin/recorder ]; then
    echo ""
    echo "NOTICE: Please restart your terminal or run: export PATH=\"$BIN_DIR:\$PATH\""
fi

echo "========================================"
