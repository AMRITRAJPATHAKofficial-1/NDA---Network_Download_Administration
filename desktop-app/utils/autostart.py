import sys
import os

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "MyDownloader"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_launch_command():
    if getattr(sys, "frozen", False):
        # Running as a packaged .exe (PyInstaller)
        return f'"{sys.executable}"'
    script_path = os.path.abspath(sys.argv[0])
    return f'"{sys.executable}" "{script_path}"'


def is_autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False


def set_autostart_enabled(enabled: bool):
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_launch_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        print(f"Failed to update autostart: {e}")
        return False