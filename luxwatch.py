import sys
import json
import subprocess
import os
import shutil
import argparse
from PyQt6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QDialog,
                             QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QSpinBox, QLineEdit, QScrollArea,
                             QWidget, QFrame, QSplitter, QCheckBox, QInputDialog, QMessageBox)
from PyQt6.QtGui import QIcon, QAction, QColor, QPalette
from PyQt6.QtCore import QTimer, Qt

# --- Constants ---
APP_NAME = "LuxWatch"
APP_VERSION = "1.4"
CONFIG_VERSION = 1
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.expanduser("~/.config/luxwatch_config.json")
ICON_ACTIVE = os.path.join(BASE_DIR, "tray_active.svg")
ICON_INACTIVE = os.path.join(BASE_DIR, "tray_inactive.svg")

# Wrappers that we allow deep scanning for
SAFE_WRAPPERS = [
    "bwrap", "flatpak", "distrobox", "distrobox-enter",
    "pressure-vessel-adverb", "steam", "python", "python3", "sh", "bash",
    "gamescope", "mangoapp", "mangohud" # Added gamescope as it wraps other apps too
]

# Paths that frequently appear in bwrap args but are NOT the app itself
IGNORE_PREFIXES = [
    "/var/lib/flatpak",
    "/usr/lib/extensions",
    "/run/flatpak"
]

# --- Backend Logic ---

class ConfigManager:
    def __init__(self):
        self.data = self.load_config()

    def load_config(self):
        defaults = {
            "config_version": CONFIG_VERSION,
            "desktop_profile": { "monitors": {} },
            "game_profiles": []
        }

        if not os.path.exists(CONFIG_FILE):
            return defaults

        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)

            file_version = data.get("config_version", 0)

            if file_version < CONFIG_VERSION:
                print(f"Migrating config from v{file_version} to v{CONFIG_VERSION}...")
                shutil.copy(CONFIG_FILE, CONFIG_FILE + ".bak")

                if file_version == 0:
                    if "profiles" in data and "desktop_profile" not in data:
                        return self.migrate_wip_to_v1(data)
                    if "desktop_profile" in data:
                        data["config_version"] = 1
                        return data
                    if "games" in data:
                         return self.migrate_alpha_to_v1(data)
            return data

        except Exception as e:
            print(f"Config load error: {e}")
            return defaults

    def migrate_wip_to_v1(self, old_data):
        desktop_mons = {}
        game_profiles = []
        old_profiles = old_data.get("profiles", [])

        if old_profiles:
            first = old_profiles[0]
            for mon, settings in first.get("monitors", {}).items():
                desktop_mons[mon] = settings.get("inactive_brightness", 70)

            for p in old_profiles:
                new_p = {
                    "name": p["name"],
                    "triggers": p.get("triggers", []),
                    "monitors": {}
                }
                for mon, settings in p.get("monitors", {}).items():
                    new_p["monitors"][mon] = {
                        "brightness": settings.get("active_brightness", 100),
                        "enabled": settings.get("enabled", True)
                    }
                game_profiles.append(new_p)

        return {
            "config_version": 1,
            "desktop_profile": { "monitors": desktop_mons },
            "game_profiles": game_profiles
        }

    def migrate_alpha_to_v1(self, old_data):
        game_profile = {
            "name": "Imported Games",
            "triggers": old_data.get("games", []),
            "monitors": {}
        }
        for mon, settings in old_data.get("monitors", {}).items():
             game_profile["monitors"][mon] = {
                 "brightness": settings.get("game", 100),
                 "enabled": True
             }

        return {
            "config_version": 1,
            "desktop_profile": { "monitors": {} },
            "game_profiles": [game_profile]
        }

    def save_config(self):
        self.data["config_version"] = CONFIG_VERSION
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get_desktop_settings(self):
        return self.data["desktop_profile"]

    def get_game_profiles(self):
        return self.data["game_profiles"]

    def add_profile(self, name):
        new_profile = {
            "name": name,
            "triggers": [],
            "monitors": {}
        }
        self.data["game_profiles"].append(new_profile)
        self.save_config()

    def delete_profile(self, index):
        if 0 <= index < len(self.data["game_profiles"]):
            del self.data["game_profiles"][index]
            self.save_config()

# --- Main App ---

class LuxWatch(QSystemTrayIcon):
    def __init__(self, app, debug=False):
        super().__init__()
        self.app = app
        self.debug = debug
        self.cfg_manager = ConfigManager()

        self.current_state = "unknown"
        self.active_profile_name = None

        self.update_tray_icon("desktop")

        self.setToolTip(f"{APP_NAME} v{APP_VERSION}: Ready")
        self.setup_menu()

        self.settings_window = SettingsWindow(self)

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_processes)
        self.timer.start(3000)

        self.show()
        print(f"{APP_NAME} v{APP_VERSION} started. Debug: {self.debug}")

    def update_tray_icon(self, state):
        icon_path = ICON_ACTIVE if state == "game" else ICON_INACTIVE
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setIcon(QIcon.fromTheme("video-display"))

    def log(self, message):
        if self.debug:
            print(f"[DEBUG] {message}", flush=True)

    def get_connected_monitors(self):
        monitors = []
        try:
            output = subprocess.check_output(["kscreen-doctor", "-j"]).decode("utf-8")
            data = json.loads(output)
            if "outputs" in data:
                for out in data["outputs"]:
                    if out.get("connected", False):
                        name = out.get("name")
                        if name: monitors.append(name)
        except Exception:
            try:
                output = subprocess.check_output(["kscreen-doctor", "-o"]).decode("utf-8")
                for line in output.splitlines():
                    if "Output:" in line and "connected" in line:
                        parts = line.split()
                        if len(parts) >= 3: monitors.append(parts[2])
            except: pass

        if not monitors:
            monitors = ["HDMI-A-1", "DP-1", "DP-2", "DP-3"]

        return sorted(monitors)

    def setup_menu(self):
        menu = QMenu()
        settings_action = QAction("Configuration...", self)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)
        self.setContextMenu(menu)

    def open_settings(self):
        self.settings_window.refresh_all()
        self.settings_window.show()

    def set_brightness(self, monitor_id, level):
        try:
            level = max(0, min(100, int(level)))
            cmd = ["kscreen-doctor", f"output.{monitor_id}.brightness.{level}"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.log(f"Failed to set brightness: {e}")

    def check_processes(self):
        if self.debug: print(".", end="", flush=True)

        try:
            # Atomic Call: Get ONLY args (full command line) for all processes
            # This avoids the race condition of calling 'comm' then 'args'
            out_args = subprocess.check_output(["ps", "-A", "-o", "args="]).decode("utf-8").splitlines()

            found_profile = None
            trigger_app = None

            for profile in self.cfg_manager.get_game_profiles():
                for trigger in profile["triggers"]:
                    trigger_lower = trigger.lower()

                    for full_args in out_args:
                        full_args = full_args.strip()
                        if not full_args: continue

                        # Split into tokens (e.g. ['/usr/bin/python', 'myscript.py'])
                        tokens = full_args.split()
                        if not tokens: continue

                        # 0. Identify the "Main Executable" (First token)
                        # os.path.basename handles '/usr/bin/gamescope' -> 'gamescope'
                        exe_name = os.path.basename(tokens[0]).lower()

                        # 1. Direct Match: The executable IS the trigger
                        if exe_name == trigger_lower:
                            found_profile = profile
                            trigger_app = exe_name
                            break

                        # 2. Wrapper Match: If exe is a wrapper, scan the rest of the tokens
                        if exe_name in SAFE_WRAPPERS:
                            # Scan remaining tokens (arguments)
                            for token in tokens[1:]:
                                token_base = os.path.basename(token).lower()

                                if token_base == trigger_lower:
                                    # FILTER: Ignore known Flatpak noise
                                    if any(token.startswith(prefix) for prefix in IGNORE_PREFIXES):
                                        continue

                                    found_profile = profile
                                    trigger_app = (full_args[:40] + '...') if len(full_args) > 40 else full_args
                                    break
                            if found_profile: break

                    if found_profile: break
                if found_profile: break

            if found_profile:
                if self.active_profile_name != found_profile["name"] or self.current_state != "game":
                    self.log(f"\nMatch: Profile '{found_profile['name']}' (Trigger: {trigger_app})")
                    self.apply_game_profile(found_profile)
                    self.active_profile_name = found_profile["name"]
                    self.current_state = "game"
                    self.update_tray_icon("game")
            else:
                if self.current_state != "desktop":
                    self.log(f"\nGame Closed. Reverting to Desktop Defaults.")
                    self.apply_desktop_profile()
                    self.active_profile_name = None
                    self.current_state = "desktop"
                    self.update_tray_icon("desktop")

        except Exception as e:
            print(f"\nError scanning: {e}")

    def apply_desktop_profile(self):
        connected = self.get_connected_monitors()
        settings = self.cfg_manager.get_desktop_settings()["monitors"]

        for mon in connected:
            level = settings.get(mon, 70)
            self.set_brightness(mon, level)

        self.setToolTip(f"{APP_NAME}: Desktop\nStandard Brightness")

    def apply_game_profile(self, profile):
        connected = self.get_connected_monitors()

        for mon in connected:
            m_conf = profile["monitors"].get(mon, {"brightness": 100, "enabled": True})

            if not m_conf.get("enabled", True):
                self.set_brightness(mon, 0)
            else:
                self.set_brightness(mon, m_conf.get("brightness", 100))

        self.setToolTip(f"{APP_NAME}: Gaming\nProfile: {profile['name']}")

# --- GUI Implementation ---

class SettingsWindow(QDialog):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.setWindowTitle(f"{APP_NAME} Configuration")
        self.resize(800, 500)

        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # LEFT PANE
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0,0,0,0)
        left_widget.setLayout(left_layout)

        left_layout.addWidget(QLabel("<b>Profiles</b>"))
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self.load_profile_details)
        left_layout.addWidget(self.profile_list)

        btn_box = QHBoxLayout()
        btn_add = QPushButton("+")
        btn_add.clicked.connect(self.create_profile)
        btn_del = QPushButton("-")
        btn_del.clicked.connect(self.delete_profile)
        btn_box.addWidget(btn_add)
        btn_box.addWidget(btn_del)
        left_layout.addLayout(btn_box)

        splitter.addWidget(left_widget)

        # RIGHT PANE
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout()
        self.right_widget.setLayout(self.right_layout)
        splitter.addWidget(self.right_widget)
        splitter.setStretchFactor(1, 3)

        self.current_selection_index = -1
        self.monitor_inputs = {}

    def refresh_all(self):
        self.profile_list.clear()
        self.profile_list.addItem("Default / Desktop")

        profiles = self.main_app.cfg_manager.get_game_profiles()
        for p in profiles:
            self.profile_list.addItem(p["name"])

        self.profile_list.setCurrentRow(0)

    def create_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Profile Name:")
        if ok and name:
            self.main_app.cfg_manager.add_profile(name)
            self.refresh_all()
            self.profile_list.setCurrentRow(self.profile_list.count() - 1)

    def delete_profile(self):
        row = self.profile_list.currentRow()
        if row == 0:
            QMessageBox.warning(self, "Locked", "Cannot delete the Default Desktop profile.")
            return

        if row > 0:
            confirm = QMessageBox.question(self, "Confirm", "Delete this profile?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                self.main_app.cfg_manager.delete_profile(row - 1)
                self.refresh_all()

    def clear_right_pane(self):
        while self.right_layout.count():
            item = self.right_layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()
            elif item.layout(): self.clear_nested_layout(item.layout())

    def clear_nested_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout(): self.clear_nested_layout(item.layout())

    def load_profile_details(self, row):
        self.clear_right_pane()
        if row < 0: return

        self.current_selection_index = row
        self.monitor_inputs = {}
        connected = self.main_app.get_connected_monitors()

        if row == 0:
            self.build_desktop_ui(connected)
        else:
            profile_data = self.main_app.cfg_manager.get_game_profiles()[row - 1]
            self.build_game_ui(profile_data, connected)

    def build_desktop_ui(self, connected):
        header = QLabel("<h2>Default / Desktop Settings</h2>")
        self.right_layout.addWidget(header)
        self.right_layout.addWidget(QLabel("Brightness levels when <b>no games</b> are running."))
        self.right_layout.addSpacing(15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        mon_container = QWidget()
        mon_layout = QVBoxLayout()
        mon_container.setLayout(mon_layout)
        scroll.setWidget(mon_container)
        self.right_layout.addWidget(scroll)

        current_settings = self.main_app.cfg_manager.get_desktop_settings()["monitors"]

        for mon_id in connected:
            val = current_settings.get(mon_id, 70)

            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setStyleSheet("QFrame { background-color: #2a2a2a; border-radius: 5px; margin-bottom: 5px; } QLabel { color: white; }")
            row = QHBoxLayout()
            frame.setLayout(row)

            row.addWidget(QLabel(f"<b>{mon_id}</b>"))
            sp = QSpinBox()
            sp.setRange(0, 100)
            sp.setValue(val)
            sp.setSuffix("%")
            row.addWidget(sp)
            mon_layout.addWidget(frame)
            self.monitor_inputs[mon_id] = sp

        self.add_save_button()

    def build_game_ui(self, profile_data, connected):
        header = QLabel(f"<h2>{profile_data['name']} Settings</h2>")
        self.right_layout.addWidget(header)

        self.right_layout.addWidget(QLabel("<b>Triggers</b> (Process names)"))
        trigger_box = QHBoxLayout()
        self.txt_trigger = QLineEdit()
        self.txt_trigger.setPlaceholderText("e.g. cyberpunk")
        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self.add_trigger)
        trigger_box.addWidget(self.txt_trigger)
        trigger_box.addWidget(btn_add)
        self.right_layout.addLayout(trigger_box)

        self.trigger_list = QListWidget()
        self.trigger_list.setFixedHeight(80)
        self.trigger_list.addItems(profile_data["triggers"])
        self.trigger_list.itemDoubleClicked.connect(self.remove_trigger)
        self.right_layout.addWidget(self.trigger_list)

        self.right_layout.addSpacing(15)

        self.right_layout.addWidget(QLabel("<b>Monitor Configuration</b>"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        mon_container = QWidget()
        mon_layout = QVBoxLayout()
        mon_container.setLayout(mon_layout)
        scroll.setWidget(mon_container)
        self.right_layout.addWidget(scroll)

        for mon_id in connected:
            m_conf = profile_data["monitors"].get(mon_id, {"brightness": 100, "enabled": True})

            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setStyleSheet("QFrame { background-color: #2a2a2a; border-radius: 5px; margin-bottom: 5px; } QLabel { color: white; } QCheckBox { color: white; }")
            row = QHBoxLayout()
            frame.setLayout(row)

            chk = QCheckBox(mon_id)
            chk.setChecked(m_conf.get("enabled", True))
            row.addWidget(chk)
            row.addWidget(QLabel("Brightness:"))
            sp = QSpinBox()
            sp.setRange(0, 100)
            sp.setValue(m_conf.get("brightness", 100))
            sp.setSuffix("%")
            row.addWidget(sp)
            mon_layout.addWidget(frame)
            self.monitor_inputs[mon_id] = {"val": sp, "chk": chk}

        self.add_save_button()

    def add_save_button(self):
        btn_save = QPushButton("Save Settings")
        btn_save.setStyleSheet("background-color: #3daee9; color: white; font-weight: bold; padding: 5px;")
        btn_save.clicked.connect(self.save_current)
        self.right_layout.addWidget(btn_save)

    def add_trigger(self):
        text = self.txt_trigger.text().strip()
        if text:
            self.trigger_list.addItem(text)
            self.txt_trigger.clear()

    def remove_trigger(self, item):
        self.trigger_list.takeItem(self.trigger_list.row(item))

    def save_current(self):
        if self.current_selection_index == 0:
            settings = self.main_app.cfg_manager.get_desktop_settings()
            for mon_id, spinbox in self.monitor_inputs.items():
                settings["monitors"][mon_id] = spinbox.value()
            QMessageBox.information(self, "Saved", "Desktop defaults updated.")
            if self.main_app.current_state == "desktop":
                self.main_app.apply_desktop_profile()
        else:
            idx = self.current_selection_index - 1
            profile = self.main_app.cfg_manager.get_game_profiles()[idx]
            triggers = []
            for i in range(self.trigger_list.count()):
                triggers.append(self.trigger_list.item(i).text())
            profile["triggers"] = triggers
            for mon_id, widgets in self.monitor_inputs.items():
                profile["monitors"][mon_id] = {
                    "brightness": widgets["val"].value(),
                    "enabled": widgets["chk"].isChecked()
                }
            QMessageBox.information(self, "Saved", f"Profile '{profile['name']}' updated.")
            if self.main_app.active_profile_name == profile["name"]:
                self.main_app.apply_game_profile(profile)

        self.main_app.cfg_manager.save_config()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)

    app.setQuitOnLastWindowClosed(False)
    tray = LuxWatch(app, debug=args.debug)
    sys.exit(app.exec())
