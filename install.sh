#!/bin/bash

# Detect Fedora and redirect to fedora_setup.sh
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" = "fedora" ]; then
        echo "===================================================="
        echo "Fedora detected!"
        echo "Please run ./fedora_setup.sh with your normal user (without sudo)."
        echo "===================================================="
        exit 1
    fi
fi

# Check for Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Python is not installed. Please install it."
    echo "On Debian/Ubuntu: sudo apt-get install python3 python3-venv"
    echo "On Arch Linux: sudo pacman -S python"
    echo "On Fedora: sudo dnf install python3"
    exit 1
fi

# Determine python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Check for jq
if ! command -v jq &> /dev/null; then
    echo "jq is not installed. Please install it."
    echo "On Debian/Ubuntu: sudo apt-get install jq"
    echo "On Arch Linux: sudo pacman -S jq"
    echo "On Fedora: sudo dnf install jq"
    exit 1
fi

# Check for root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit
fi

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Get the user who ran sudo
SUDO_USER=${SUDO_USER:-$USER}

# Create virtual environment if it doesn't exist
VENV_DIR="${SCRIPT_DIR}/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating Python virtual environment..."
  # Run as the actual user, not root
  sudo -u "$SUDO_USER" "$PYTHON_CMD" -m venv "$VENV_DIR"

  if [ $? -ne 0 ]; then
    echo "Failed to create virtual environment."
    echo "Make sure python3-venv is installed:"
    echo "On Debian/Ubuntu: sudo apt-get install python3-venv"
    exit 1
  fi

  echo "Virtual environment created at $VENV_DIR"

  # Install requirements if requirements.txt exists
  if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
    echo "Installing Python dependencies..."
    sudo -u "$SUDO_USER" "$VENV_DIR/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt"

    if [ $? -ne 0 ]; then
      echo "Warning: Failed to install some dependencies. Please check requirements.txt"
    fi
  else
    echo "No requirements.txt found. Skipping dependency installation."
  fi
else
  echo "Virtual environment already exists at $VENV_DIR"
fi

# Verify Python executable exists in venv
if [ ! -f "$VENV_DIR/bin/python" ]; then
  echo "Error: Virtual environment Python executable not found at $VENV_DIR/bin/python"
  exit 1
fi

# Create udev rule
UDEV_RULE_FILE="/etc/udev/rules.d/70-digital-thermal-right-lcd.rules"
if [ ! -f "$UDEV_RULE_FILE" ]; then
  echo "Creating udev rule at $UDEV_RULE_FILE"
  echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="8001", MODE="0666"' > "$UDEV_RULE_FILE"
  echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="8001", TAG+="uaccess"' >> "$UDEV_RULE_FILE"
  udevadm control --reload-rules
  udevadm trigger
  echo "udev rule created."
else
  echo "udev rule already exists."
fi

# Create systemd service
SERVICE_FILE="/etc/systemd/system/digital-thermal-right-lcd.service"
echo "Creating systemd service at $SERVICE_FILE"

cat > "$SERVICE_FILE" << EOL
[Unit]
Description=Digital Thermal Right LCD Controller
After=network.target

[Service]
ExecStart=${VENV_DIR}/bin/python ${SCRIPT_DIR}/src/controller.py
WorkingDirectory=${SCRIPT_DIR}
Restart=always
User=${SUDO_USER}

[Install]
WantedBy=multi-user.target
EOL

echo "Systemd service file created."

# Reload systemd, enable and start the service
echo "Reloading systemd, enabling and starting the service."
systemctl daemon-reload
systemctl enable digital-thermal-right-lcd.service
systemctl start digital-thermal-right-lcd.service

# Make scripts executable
chmod +x "${SCRIPT_DIR}/install.sh"
chmod +x "${SCRIPT_DIR}/uninstall.sh"
chmod +x "${SCRIPT_DIR}/led_control.sh"

echo ""
echo "Installation complete."
echo ""
echo "Service status:"
systemctl status digital-thermal-right-lcd.service --no-pager
