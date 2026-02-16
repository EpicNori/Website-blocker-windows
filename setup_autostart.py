"""
Autostart Setup for Website & App Blocker
Uses Windows Task Scheduler to run the blocker at logon with admin privileges
(no UAC prompt needed). Falls back to the registry method if schtasks fails.
"""

import ctypes
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLOCKER_SCRIPT = os.path.join(SCRIPT_DIR, "blocker.py")
TASK_NAME = "WebsiteAppBlocker"


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
    return sys.executable


def add_to_startup():
    """Add the blocker to Windows startup via Task Scheduler (runs elevated)."""
    pythonw = find_pythonw()

    # Remove any existing task first (ignore errors)
    subprocess.call(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Create a scheduled task that runs at logon with highest privileges.
    # /RL HIGHEST = run with admin rights, no UAC prompt.
    # /DELAY 0000:15 = wait 15 seconds after logon so the network is ready.
    result = subprocess.call(
        [
            "schtasks", "/Create",
            "/TN", TASK_NAME,
            "/TR", f'"{pythonw}" "{BLOCKER_SCRIPT}" daemon',
            "/SC", "ONLOGON",
            "/RL", "HIGHEST",
            "/DELAY", "0000:15",
            "/F",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result == 0:
        print("Website & App Blocker added to Windows startup (Task Scheduler).")
        print(f"Task name: {TASK_NAME}")
        print(f"Command:   \"{pythonw}\" \"{BLOCKER_SCRIPT}\" daemon")
        print("\nThe blocker will run automatically with admin rights when you log in.")
        print("No UAC prompt will appear.")
    else:
        print("Task Scheduler failed. Falling back to registry method...")
        _add_to_startup_registry(pythonw)


def _add_to_startup_registry(pythonw):
    """Fallback: add to startup via the registry (may show UAC prompt on login)."""
    import winreg

    reg_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    command = f'"{pythonw}" "{BLOCKER_SCRIPT}" daemon'

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, reg_key, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, TASK_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        print("Website & App Blocker added to Windows startup (registry).")
        print(f"Command: {command}")
        print("\nNote: You may see a UAC prompt on login since the registry")
        print("method can't auto-elevate. The Task Scheduler method is preferred.")
    except Exception as e:
        print(f"Error adding to startup: {e}")


def remove_from_startup():
    """Remove the blocker from both Task Scheduler and registry."""
    removed = False

    # Remove from Task Scheduler
    result = subprocess.call(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result == 0:
        print("Removed from Task Scheduler.")
        removed = True

    # Also remove from registry (in case it was set by an older version)
    try:
        import winreg

        reg_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, reg_key, 0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, TASK_NAME)
        winreg.CloseKey(key)
        print("Removed from registry startup.")
        removed = True
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Also try the old registry name
    try:
        import winreg

        reg_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, reg_key, 0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, "WebsiteBlocker")
        winreg.CloseKey(key)
        print("Removed old 'WebsiteBlocker' registry entry.")
        removed = True
    except FileNotFoundError:
        pass
    except Exception:
        pass

    if not removed:
        print("Website & App Blocker was not in startup.")


def check_startup():
    """Check if the blocker is configured to start automatically."""
    found = False

    # Check Task Scheduler
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"Task Scheduler: ACTIVE (task '{TASK_NAME}')")
        # Show some details
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and TASK_NAME in line:
                print(f"  {line}")
        found = True
    else:
        print("Task Scheduler: not configured")

    # Check registry
    try:
        import winreg

        reg_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, reg_key, 0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, TASK_NAME)
        winreg.CloseKey(key)
        print(f"Registry: ACTIVE")
        print(f"  Command: {value}")
        found = True
    except FileNotFoundError:
        print("Registry: not configured")
    except Exception:
        print("Registry: not configured")

    if not found:
        print("\nWebsite & App Blocker is NOT configured to start automatically.")

    return found


def main():
    if len(sys.argv) < 2:
        print("Autostart Setup for Website & App Blocker")
        print("-" * 45)
        print("Usage:")
        print("  python setup_autostart.py install   - Add to Windows startup")
        print("  python setup_autostart.py uninstall - Remove from Windows startup")
        print("  python setup_autostart.py status    - Check if in startup")
        return

    command = sys.argv[1].lower()

    if command == "status":
        check_startup()
        return

    # install/uninstall need admin for Task Scheduler
    if not is_admin():
        print("Requesting administrator privileges...")
        run_as_admin()
        return

    if command == "install":
        add_to_startup()

    elif command == "uninstall":
        remove_from_startup()

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
