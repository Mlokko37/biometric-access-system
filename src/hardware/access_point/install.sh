#!/bin/bash
# Installation script for Raspberry Pi access point

set -e

echo "========================================="
echo "Face Recognition Access Point Installer"
echo "========================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: Not running on a Raspberry Pi"
    echo "Continuing anyway (simulation mode)..."
fi

# Update system
echo "Updating system..."
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-opencv \
    python3-picamera2 \
    libatlas-base-dev \
    libjpeg-dev \
    libtiff5-dev \
    libhdf5-dev \
    libopenblas-dev \
    git \
    cmake \
    build-essential

# Create virtual environment (optional)
# python3 -m venv venv
# source venv/bin/activate

# Install Python packages
echo "Installing Python packages..."
pip3 install -r requirements.txt

# Create directories
echo "Creating directories..."
sudo mkdir -p /var/log/access_point
sudo mkdir -p /etc/access_point
sudo chmod 755 /var/log/access_point

# Copy config file if it doesn't exist
if [ ! -f /etc/access_point/config.yaml ]; then
    echo "Creating default config..."
    sudo cp config.yaml /etc/access_point/config.yaml
fi

# Setup systemd service
echo "Setting up systemd service..."
sudo cp access_point.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable access_point

echo "Installation complete!"
echo ""
echo "To start the service:"
echo "  sudo systemctl start access_point"
echo ""
echo "To check status:"
echo "  sudo systemctl status access_point"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u access_point -f"
echo ""
echo "========================================="
echo "Installation completed successfully!"
echo "========================================="