# LuxWatch

**LuxWatch** is a lightweight, system-tray utility for Linux (KDE Plasma 6 / Wayland) that automatically manages monitor brightness based on the running application.

It is designed for gaming setups where you want your main monitor to be 100% brightness while gaming, but dimmed to 70% (or lower) for desktop use to reduce eye strain.

## Features
* **Profile Support:** Create custom profiles for "Horror Games" (secondary screens off), "Work", or "Movies".
* **Smart Detection:** Detects games even if they are running inside Flatpak, Bubblewrap, or Steam Proton.
* **Multi-Monitor:** Individual control for every connected display.
* **Tray Icon:** Active/Inactive states indicated by the tray icon color.
* **Safe:** Runs in user-space using standard KDE tools (`kscreen-doctor`).

## Installation

1.  Clone this repository:
    ```bash
    git clone https://github.com/YOUR_USERNAME/LuxWatch.git
    cd LuxWatch
    ```

2.  Run the installer:
    ```bash
    chmod +x install.sh
    ./install.sh
    ```

3.  Log out and log back in (or start it manually from your application menu).

## Requirements
* Python 3
* PyQt6
* KDE Plasma 6 (Wayland)
* `kscreen-doctor` (Standard on KDE)
* `ddcutil` (Optional, for hardware debugging)

## License
MIT
