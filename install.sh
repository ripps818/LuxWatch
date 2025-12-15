#!/bin/bash

# LuxWatch Installer v1.1
# Updates/Overwrites existing installation by default.

APP_DIR="$HOME/LuxWatch"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APP_DIR_LOCAL="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"

# Check for flags
FORCE=false
for arg in "$@"; do
    if [ "$arg" == "--force" ] || [ "$arg" == "-f" ]; then
        FORCE=true
    fi
done

echo ">>> Installing LuxWatch..."

# 1. Setup Directory
mkdir -p "$APP_DIR"

# Always overwrite the main script to ensure updates are applied
echo "Copying/Updating luxwatch.py..."
cp -f luxwatch.py "$APP_DIR/"

# 2. Setup/Update Virtual Environment
if [ ! -d "$APP_DIR/venv" ] || [ "$FORCE" = true ]; then
    echo ">>> Setting up Virtual Environment..."
    cd "$APP_DIR"
    python3 -m venv venv
    source venv/bin/activate
    pip install PyQt6 --quiet
else
    echo ">>> Virtual Environment exists. Skipping setup (use --force to reinstall venv)."
fi

# 3. Generate Icons (Overwrite always to ensure new styles apply)
mkdir -p "$ICON_DIR"
echo ">>> Updating Icons..."

# APP ICON (Color)
cat > "$ICON_DIR/luxwatch.svg" << EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="4" y="8" width="56" height="36" rx="3" fill="#333" stroke="#222" stroke-width="2"/>
  <path d="M24 48 L28 44 L36 44 L40 48" fill="#333"/>
  <rect x="20" y="48" width="24" height="4" rx="2" fill="#222"/>
  <circle cx="32" cy="26" r="6" fill="#FFD700"/>
  <path d="M32 14 V18 M32 34 V38 M14 26 H18 M46 26 H50 M20 14 L23 17 M44 38 L41 35 M20 38 L23 35 M44 14 L41 17" stroke="#FFD700" stroke-width="3" stroke-linecap="round"/>
</svg>
EOF

# TRAY: INACTIVE (Dark Grey Monitor, BLACK Sun)
cat > "$APP_DIR/tray_inactive.svg" << EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="4" y="8" width="56" height="36" rx="3" fill="none" stroke="#888" stroke-width="4"/>
  <path d="M26 48 L28 44 L36 44 L38 48" fill="none" stroke="#888" stroke-width="4"/>
  <line x1="18" y1="48" x2="46" y2="48" stroke="#888" stroke-width="4" stroke-linecap="round"/>
  <circle cx="32" cy="26" r="5" fill="#000000"/>
  <path d="M32 16 V20 M32 32 V36 M16 26 H20 M44 26 H48" stroke="#000000" stroke-width="3" stroke-linecap="round"/>
</svg>
EOF

# TRAY: ACTIVE (White Monitor, WHITE Sun)
cat > "$APP_DIR/tray_active.svg" << EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="4" y="8" width="56" height="36" rx="3" fill="#eee" stroke="#fff" stroke-width="2"/>
  <path d="M26 48 L28 44 L36 44 L38 48" fill="#fff"/>
  <rect x="18" y="48" width="28" height="4" rx="2" fill="#fff"/>
  <circle cx="32" cy="26" r="7" fill="#333"/>
  <path d="M32 12 V18 M32 34 V40 M12 26 H18 M46 26 H52 M18 12 L22 16 M46 40 L42 36 M18 40 L22 36 M46 12 L42 16" stroke="#333" stroke-width="3" stroke-linecap="round"/>
</svg>
EOF

# 4. Update .desktop file
echo ">>> Updating Menu Shortcut..."
mkdir -p "$APP_DIR_LOCAL"

cat > "$APP_DIR_LOCAL/luxwatch.desktop" << EOF
[Desktop Entry]
Name=LuxWatch
Comment=Auto-Brightness for Games
Exec=$APP_DIR/venv/bin/python $APP_DIR/luxwatch.py
Icon=luxwatch
Terminal=false
Type=Application
Categories=Utility;Settings;
EOF

# 5. Update Autostart
echo ">>> Updating Autostart..."
mkdir -p "$AUTOSTART_DIR"
cp -f "$APP_DIR_LOCAL/luxwatch.desktop" "$AUTOSTART_DIR/luxwatch.desktop"

# Refresh icon cache
touch "$ICON_DIR"

echo "------------------------------------------------"
echo "UPDATE COMPLETE!"
echo "Files have been overwritten with the latest version."
echo "Please restart LuxWatch for changes to take effect."
echo "------------------------------------------------"
