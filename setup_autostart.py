"""
Autostart Setup for Website Blocker
Adds or removes the website blocker from Windows startup.
"""

import ctypes
import os
import sys
import winreg

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLOCKER_SCRIPT = os.path.join(SCRIPT_DIR, "blocker.py")
STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WebsiteBlocker"


def is_admin():
    """Check if running as administrator."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Re-launch with admin privileges."""
    script = os.path.abspath(__file__)
    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 0
    )
    sys.exit(0)


def find_pythonw():
    """Find pythonw.exe path for silent execution."""
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    # Fallback to python.exe
    return sys.executable


def add_to_startup():
    """Add the website blocker to Windows startup via registry."""
    pythonw = find_pythonw()
    # Use daemon mode so it keeps re-applying blocks
    command = f'"{pythonw}" "{BLOCKER_SCRIPT}" daemon'

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        print("Website Blocker added to Windows startup.")
        print(f"Command: {command}")
        print("\nThe blocker will run automatically when you log in.")
    except Exception as e:
        print(f"Error adding to startup: {e}")


def remove_from_startup():
    """Remove the website blocker from Windows startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("Website Blocker removed from Windows startup.")
    except FileNotFoundError:
        print("Website Blocker was not in startup.")
    except Exception as e:
        print(f"Error removing from startup: {e}")


def check_startup():
    """Check if the blocker is in startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        print(f"Website Blocker IS in startup.")
        print(f"Command: {value}")
        return True
    except FileNotFoundError:
        print("Website Blocker is NOT in startup.")
        return False
    except Exception as e:
        print(f"Error checking startup: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Autostart Setup for Website Blocker")
        print("-" * 40)
        print("Usage:")
        print("  python setup_autostart.py install   - Add to Windows startup")
        print("  python setup_autostart.py uninstall - Remove from Windows startup")
        print("  python setup_autostart.py status    - Check if in startup")
        return

    command = sys.argv[1].lower()

    if command == "status":
        check_startup()
        return

    if command == "install":
        add_to_startup()

    elif command == "uninstall":
        remove_from_startup()

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
