# Digital Thermal Right LCD Controller

This project allows you to control the Thermalright USB LCD screen on Linux.
It provides a Python controller to display system metrics (CPU/GPU temp/usage) and a shell script to configure the display.

## Features

- Display CPU/GPU temperature and usage.
- Multiple display modes.
- Configurable colors and gradients.
- Animated rainbow and wave patterns.
- Configuration via a shell script menu.
- GUI for live display preview and color configuration.

## Prerequisites

- Python 3
- `jq` command-line JSON processor.
  - On Arch Linux: `sudo pacman -S jq`
  - On Debian/Ubuntu: `sudo apt-get install jq`
  - On Fedora: `sudo dnf install jq`
- `hidapi` library for your distribution.
  - On Arch Linux: `sudo pacman -S hidapi`
  - On Debian/Ubuntu: `sudo apt-get install libhidapi-dev`
- Python dependencies can be installed via `pip`.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/digital_thermal_right_lcd.git
    cd digital_thermal_right_lcd
    ```

### Option A: Standard Linux Distributions (Ubuntu, Debian, Arch...)

1.  **Create a virtual environment and install dependencies:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Run the installation script:**
    This script will set up the `udev` rule to allow running without `sudo` and create a `systemd` service to run the display controller on startup.
    ```bash
    sudo ./install.sh
    ```

### Option B: Fedora (Optimized for SELinux & System Packages)

Fedora enforces strict SELinux security policies that prevent systemd from executing binaries (including Python virtual environments) located inside user home directories. A dedicated installer is provided to use official system-wide packages and compile drivers cleanly.

1.  **Run the Fedora setup script:**
    Run this script with your **standard user account** (do NOT use `sudo ./fedora_setup.sh`; the script will prompt for your sudo password when executing system package installations):
    ```bash
    ./fedora_setup.sh
    ```
    This script will automatically install the official Fedora Python libraries (including GUI/Tkinter support), download the necessary compilation tools (`gcc`, `libdrm-devel`) to build the GPU monitor, install the required packages system-wide by bypassing PEP 668, register the `udev` rule, and start the systemd service using the official system python interpreter.

## Usage

### Configuration

To configure the display, run the `led_control.sh` script:
```bash
./led_control.sh
```
This will open a menu where you can change display modes, colors, and other settings.

### GUI

A graphical interface is available for live preview and color customization.
To run the GUI:
```bash
python src/led_display_ui.py
```

## Uninstallation

To uninstall the service and udev rule, run the `uninstall.sh` script:
```bash
sudo ./uninstall.sh
```