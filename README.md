# Thermalright Digital LCD Screen Controller for Linux (Fedora, Ubuntu, Arch)

[![Linux Support](https://img.shields.io/badge/platform-Linux-blue.svg)](https://github.com/signe22/Thermalright-Assassin-X--120-fedora-software)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An unofficial Linux driver and controller for **Thermalright Digital** CPU coolers (such as the **Thermalright TL-AX120 R Digital** and **Peerless Assassin 120 Digital** series). This project enables real-time CPU & GPU temperature and usage display on the cooler's integrated USB LCD screen under Linux, with support for customizable LED colors, animated gradients, and systemd service integration.

Special optimizations are included for **Fedora** to bypass PEP 668 restrictions and SELinux home execution blocks.

---

## Features

- 🖥️ **Dual Metric Monitoring**: Display CPU and GPU temperature and load utilization side-by-side or alternating.
- 🎨 **Rich Lighting Effects**: Configure solid colors, animated gradients (including rainbow), or dynamic metric-based color shifts (e.g., green to red as temperature rises).
- 🕒 **Time & Date Modes**: Display current time (including seconds) on the digital screen.
- ⚙️ **Dual Layout Modes**: Full compatibility with both "Big" (84 LEDs) and "Small" (31 LEDs) layouts.
- 💻 **Interactive Configuration**:
  - Command-line interactive menu (`./led_control.sh`) powered by `jq`.
  - Graphical User Interface (`python3 src/led_display_ui.py`) built with Tkinter for live preview and visual customization.
- 🐧 **Linux Services**:
  - Runs in the background as a secure, non-root systemd service.
  - Automatically reloads on startup.

---

## Prerequisites

- **Python 3.8+**
- **jq** command-line JSON processor:
  - Fedora: `sudo dnf install jq`
  - Ubuntu/Debian: `sudo apt-get install jq`
  - Arch Linux: `sudo pacman -S jq`
- **hidapi** library:
  - Fedora: `sudo dnf install python3-hidapi`
  - Ubuntu/Debian: `sudo apt-get install libhidapi-dev`
  - Arch Linux: `sudo pacman -S hidapi`

---

## Installation

First, clone this repository:
```bash
git clone https://github.com/signe22/Thermalright-Assassin-X--120-fedora-software.git
cd Thermalright-Assassin-X--120-fedora-software
```

### Option A: Fedora (Optimized for SELinux & System Packages)

Fedora enforces strict SELinux security policies that prevent systemd from executing binaries (including Python virtual environments) located inside user home directories. This project features a tailored Fedora setup script that uses system-wide libraries and compiles GPU helpers cleanly.

Run the installer with your **standard user account** (do NOT run with `sudo`; the script prompts for elevated privileges when installing system RPMs):
```bash
./fedora_setup.sh
```
This script will automatically:
1. Install system dependencies (`python3-hidapi`, `python3-numpy`, `python3-psutil`, `python3-tkinter`, `jq`, `gcc`, `libdrm-devel`).
2. Build and install GPU querying interfaces (`pyamdgpuinfo` and `pynvml`) system-wide, bypassing PEP 668.
3. Configure `udev` permissions for driver-free USB communication.
4. Deploy and start a systemd background service utilizing the official system Python interpreter to comply with SELinux policies.

### Option B: Other Linux Distributions (Ubuntu, Debian, Arch...)

For standard Linux distributions, you can use a Python virtual environment:

1. **Set up the virtual environment and install requirements**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Execute the installation script as root**:
   ```bash
   sudo ./install.sh
   ```

---

## Usage

### 🔧 Configuration Menu
Modify display modes, color maps, cycle speeds, and settings with the CLI utility:
```bash
./led_control.sh
```

### 🖥️ GUI Customizer
Run the Tkinter-based live layout preview and interactive editor:
```bash
# If using Option A (Fedora):
python3 src/led_display_ui.py

# If using Option B (Venv):
.venv/bin/python src/led_display_ui.py
```

---

## Uninstallation

To stop the service and remove the `udev` rule from your system, run:
```bash
sudo ./uninstall.sh
```

---

## Credits & Acknowledgements

This project is a fork adapted for Fedora systems. 

- **Original Project**: [raffa0001/Peerless_assassin_and_CLI_UI](https://github.com/raffa0001/Peerless_assassin_and_CLI_UI.git) - Big thanks to the original author for creating the controller framework!
- **Fedora adaptation & optimizations**: Developed by [signe22](https://github.com/signe22) to support clean, out-of-the-box installation on modern Fedora setups, ensuring SELinux policies, python-tkinter dependencies, and compiler settings compile cleanly.