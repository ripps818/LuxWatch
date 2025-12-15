#!/bin/bash

# LuxWatch Uninstaller

APP_DIR="$HOME/LuxWatch"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APP_DIR_LOCAL="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
CONFIG_FILE="$HOME/.config/luxwatch_config.json"

echo ">>> Uninstalling LuxWatch..."

# 1. Kill running process
if pgrep -f "luxwatch.py" > /dev/null; then
    echo "Stopping running LuxWatch process..."
    pkill -f "luxwatch.py"
fi

# 2. Remove .desktop files
if [ -f "$APP_DIR_LOCAL/luxwatch.desktop" ]; then
    echo "Removing menu shortcut..."
    rm "$APP_DIR_LOCAL/luxwatch.desktop"
fi

if [ -f "$AUTOSTART_DIR/luxwatch.desktop" ]; then
    echo "Removing autostart entry..."
    rm "$AUTOSTART_DIR/luxwatch.desktop"
fi

# 3. Remove App Icon
if [ -f "$ICON_DIR/luxwatch.svg" ]; then
    echo "Removing app icon..."
    rm "$ICON_DIR/luxwatch.svg"
    # Refresh icon cache timestamp so the system notices the deletion
    touch "$ICON_DIR"
fi

# 4. Remove App Directory (Source, Venv, Tray Icons)
if [ -d "$APP_DIR" ]; then
    echo "Removing application directory ($APP_DIR)..."
    rm -rf "$APP_DIR"
fi

# 5. Optional: Remove Config
if [ -f "$CONFIG_FILE" ]; then
    echo "Found configuration file at: $CONFIG_FILE"
    read -p "Do you want to delete your saved profiles and settings? [y/N] " response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])+$ ]]; then
        echo "Removing config file..."
        rm "$CONFIG_FILE"
    else
        echo "Config file kept. (You can manually delete it later)"
    fi
fi

echo "------------------------------------------------"
echo "UNINSTALL COMPLETE"
echo "LuxWatch has been removed from your system."
echo "------------------------------------------------"
