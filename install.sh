#!/usr/bin/env bash
set -e

# install.sh - installs system libraries and Python dependencies for pie-stream project

echo "Installing system dependencies..."

OS="$(uname)"
if [[ "$OS" == "Darwin" ]]; then
  # Homebrew dependencies for macOS
  if ! command -v brew >/dev/null; then
    echo "Homebrew not found. Please install Homebrew: https://brew.sh/"
    exit 1
  fi
  brew install libusb hidapi vlc
elif [[ -f /etc/debian_version ]]; then
  # Debian/Ubuntu dependencies
  sudo apt update
  sudo apt install -y libusb-1.0-0-dev libhidapi-dev vlc libvlc-dev abcde cdparanoia cd-discid vorbis-tools
else
  echo "Unsupported OS: $OS. Please install libusb, hidapi and VLC manually."
fi

# Let uv manage the virtual environment and dependencies
echo "Installing Python dependencies via uv..."
pip install --upgrade pip uv
uv install

echo "Installation complete. Enter the environment with 'uv shell'."
