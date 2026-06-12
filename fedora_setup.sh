#!/bin/bash

# Exit on any error
set -e

# Terminal colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}   Fedora Setup - Thermalright TL-AX120 R Digital   ${NC}"
echo -e "${CYAN}====================================================${NC}"

# Check for root / sudo
if [ "$EUID" -eq 0 ]; then
    CURRENT_USER=$(logname 2>/dev/null || echo $USER)
    echo -e "${RED}Please do NOT run this script directly as root.${NC}"
    echo -e "${YELLOW}Run it with your standard user ($CURRENT_USER). The script will prompt for your sudo password to install system packages.${NC}"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SUDO_USER=${SUDO_USER:-$USER}

echo -e "\n${YELLOW}[1/5] Installing official Fedora packages (system, compilation & GUI)...${NC}"
sudo dnf install -y python3-hidapi python3-numpy python3-psutil python3-tkinter jq gcc python3-devel libdrm-devel python3-pip

echo -e "\n${GREEN}[✔] Fedora system packages installed!${NC}"

echo -e "\n${YELLOW}[2/5] Installing Python modules for GPU monitoring (AMD & NVIDIA)...${NC}"
# Use --break-system-packages because Fedora enforces PEP 668 (externally-managed-environment)
sudo pip3 install --break-system-packages pyamdgpuinfo pynvml || {
    echo -e "${YELLOW}[!] Warning: Failed to install pyamdgpuinfo or pynvml.${NC}"
    echo -e "${YELLOW}If you do not use a dedicated graphics card or are offline, you can safely ignore this.${NC}"
}

echo -e "\n${YELLOW}[3/5] Configuring USB access rules (udev)...${NC}"
UDEV_RULE_FILE="/etc/udev/rules.d/70-digital-thermal-right-lcd.rules"

sudo bash -c "cat > $UDEV_RULE_FILE" << EOL
SUBSYSTEM=="usb", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="8001", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="8001", TAG+="uaccess"
EOL

sudo udevadm control --reload-rules
sudo udevadm trigger
echo -e "${GREEN}[✔] udev rules configured.${NC}"

echo -e "\n${YELLOW}[4/5] Deploying secure systemd service for Fedora...${NC}"
SERVICE_FILE="/etc/systemd/system/digital-thermal-right-lcd.service"

# We use the official system python interpreter to bypass SELinux home execution block!
# We also use python3 -u (unbuffered) so logs are written immediately to systemd journal.
sudo bash -c "cat > $SERVICE_FILE" << EOL
[Unit]
Description=Digital Thermal Right LCD Controller
After=network.target

[Service]
ExecStart=/usr/bin/python3 -u ${SCRIPT_DIR}/src/controller.py
WorkingDirectory=${SCRIPT_DIR}
Restart=always
User=${SUDO_USER}

[Install]
WantedBy=multi-user.target
EOL

echo -e "${GREEN}[✔] systemd service file created.${NC}"

echo -e "\n${YELLOW}[5/5] Enabling and starting the service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable digital-thermal-right-lcd.service
sudo systemctl restart digital-thermal-right-lcd.service

# Make other scripts executable
chmod +x led_control.sh uninstall.sh install.sh fedora_setup.sh

echo -e "\n${YELLOW}Waiting for display initialization (3s)...${NC}"
sleep 3

echo -e "\n${GREEN}[✔] systemd service status:${NC}"
sudo systemctl status digital-thermal-right-lcd.service --no-pager

echo -e "\n${CYAN}====================================================${NC}"
echo -e "${GREEN}🎉 Complete Success!${NC}"
echo -e "Your Thermalright TL-AX120 R display is now showing CPU/GPU temperatures in real-time."
echo -e "\nTo customize colors, speed, or test presets, run:"
echo -e "  ${YELLOW}./led_control.sh${NC}"
echo -e "====================================================${NC}"
