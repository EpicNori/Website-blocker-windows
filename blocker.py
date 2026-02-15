"""
Website & App Blocker for Windows
Blocks distracting websites via the hosts file and kills blocked apps.
Runs at startup and keeps everything blocked.
"""

import ctypes
import json
import os
import subprocess
import sys
import time

HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
BLOCK_MARKER_START = "# === WEBSITE BLOCKER START ==="
BLOCK_MARKER_END = "# === WEBSITE BLOCKER END ==="
REDIRECT_IP = "127.0.0.1"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocked_sites.json")

# Default blocked apps — process names as they appear in Task Manager
DEFAULT_BLOCKED_APPS = [
    "TikTok.exe",
    "Instagram.exe",
]


def is_admin():
    """Check if the script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Re-launch the script with administrator privileges."""
    script = os.path.abspath(__file__)
    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 0
    )
    sys.exit(0)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config():
    """Load blocked websites and apps from the config file."""
    if not os.path.exists(CONFIG_FILE):
        default_sites = [
            "www.tiktok.com",
            "tiktok.com",
            "www.youtube.com",
            "youtube.com",
            "m.youtube.com",
            "www.instagram.com",
            "instagram.com",
            "www.facebook.com",
            "facebook.com",
            "www.twitter.com",
            "twitter.com",
            "x.com",
            "www.x.com",
            "www.reddit.com",
            "reddit.com",
        ]
        save_config(default_sites, DEFAULT_BLOCKED_APPS)
        return default_sites

    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    return data.get("blocked_sites", [])


def load_blocked_apps():
    """Load the list of blocked apps from the config file."""
    if not os.path.exists(CONFIG_FILE):
        load_config()  # creates the default config

    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    return data.get("blocked_apps", [])


def load_full_config():
    """Load the full config dict."""
    if not os.path.exists(CONFIG_FILE):
        load_config()

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(sites, apps=None):
    """Save blocked websites and apps to the config file."""
    # Preserve existing apps if not provided
    if apps is None:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            apps = data.get("blocked_apps", [])
        else:
            apps = DEFAULT_BLOCKED_APPS

    with open(CONFIG_FILE, "w") as f:
        json.dump({"blocked_sites": sites, "blocked_apps": apps}, f, indent=2)


def save_blocked_apps(apps):
    """Save the blocked apps list, preserving existing sites."""
    data = load_full_config()
    data["blocked_apps"] = apps
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Website blocking (hosts file)
# ---------------------------------------------------------------------------

def read_hosts():
    """Read the current hosts file content."""
    try:
        with open(HOSTS_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def block_sites(sites):
    """Add blocked sites to the hosts file."""
    content = read_hosts()
    content = remove_blocker_entries(content)

    block_lines = [BLOCK_MARKER_START]
    for site in sites:
        block_lines.append(f"{REDIRECT_IP} {site}")
    block_lines.append(BLOCK_MARKER_END)

    new_content = content.rstrip("\n") + "\n\n" + "\n".join(block_lines) + "\n"

    with open(HOSTS_PATH, "w") as f:
        f.write(new_content)

    print(f"Blocked {len(sites)} sites.")


def unblock_sites():
    """Remove all blocker entries from the hosts file."""
    content = read_hosts()
    new_content = remove_blocker_entries(content)

    with open(HOSTS_PATH, "w") as f:
        f.write(new_content)

    print("All sites unblocked.")


def remove_blocker_entries(content):
    """Remove the blocker section from hosts file content."""
    lines = content.split("\n")
    new_lines = []
    inside_block = False

    for line in lines:
        if line.strip() == BLOCK_MARKER_START:
            inside_block = True
            continue
        if line.strip() == BLOCK_MARKER_END:
            inside_block = False
            continue
        if not inside_block:
            new_lines.append(line)

    return "\n".join(new_lines)


# ---------------------------------------------------------------------------
# App blocking (process killing)
# ---------------------------------------------------------------------------

def get_running_processes():
    """Get a set of currently running process names."""
    try:
        output = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        processes = set()
        for line in output.decode("utf-8", errors="ignore").strip().split("\n"):
            line = line.strip()
            if line:
                # CSV format: "process.exe","PID","Session","Session#","Mem"
                name = line.split(",")[0].strip('"')
                processes.add(name.lower())
        return processes
    except Exception:
        return set()


def kill_blocked_apps(apps):
    """Kill any running processes that match the blocked apps list."""
    if not apps:
        return 0

    running = get_running_processes()
    killed = 0

    for app in apps:
        if app.lower() in running:
            try:
                subprocess.call(
                    ["taskkill", "/F", "/IM", app],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                print(f"Killed blocked app: {app}")
                killed += 1
            except Exception:
                pass

    return killed


# ---------------------------------------------------------------------------
# Status / display
# ---------------------------------------------------------------------------

def show_status():
    """Show which sites and apps are currently blocked."""
    # Sites
    content = read_hosts()
    lines = content.split("\n")
    inside_block = False
    blocked = []

    for line in lines:
        if line.strip() == BLOCK_MARKER_START:
            inside_block = True
            continue
        if line.strip() == BLOCK_MARKER_END:
            inside_block = False
            continue
        if inside_block and line.strip():
            parts = line.strip().split()
            if len(parts) >= 2:
                blocked.append(parts[1])

    if blocked:
        print("Currently blocked sites:")
        for site in blocked:
            print(f"  - {site}")
    else:
        print("No sites are currently blocked.")

    # Apps
    apps = load_blocked_apps()
    if apps:
        print("\nBlocked apps (will be killed when detected):")
        for app in apps:
            print(f"  - {app}")
    else:
        print("\nNo apps are being blocked.")

    print(f"\nConfig file: {CONFIG_FILE}")


def print_usage():
    """Print usage information."""
    print("Website & App Blocker for Windows")
    print("-" * 45)
    print()
    print("Website commands:")
    print("  python blocker.py block       - Block all sites from config")
    print("  python blocker.py unblock     - Unblock all sites")
    print("  python blocker.py status      - Show blocked sites & apps")
    print("  python blocker.py add <site>  - Add a site to the block list")
    print("  python blocker.py remove <site> - Remove a site")
    print("  python blocker.py list        - List everything in config")
    print()
    print("App commands:")
    print("  python blocker.py addapp <name.exe>    - Add an app to block")
    print("  python blocker.py removeapp <name.exe> - Remove an app")
    print("  python blocker.py killapps             - Kill blocked apps now")
    print("  python blocker.py listapps             - List running processes")
    print()
    print("General:")
    print("  python blocker.py daemon    - Run in background (blocks sites + kills apps)")


def main():
    if len(sys.argv) < 2:
        command = "block"
    else:
        command = sys.argv[1].lower()

    # --- Commands that don't need admin ---

    if command == "list":
        sites = load_config()
        apps = load_blocked_apps()
        print("Blocked sites:")
        for site in sites:
            print(f"  - {site}")
        print(f"\nBlocked apps:")
        for app in apps:
            print(f"  - {app}")
        return

    if command == "status":
        show_status()
        return

    if command == "help":
        print_usage()
        return

    if command == "listapps":
        print("Currently running processes:")
        processes = get_running_processes()
        for p in sorted(processes):
            print(f"  {p}")
        print(f"\nTotal: {len(processes)} processes")
        print("\nUse the exact process name with 'addapp' to block it.")
        print("Example: python blocker.py addapp TikTok.exe")
        return

    # --- Commands that need admin ---

    if not is_admin():
        print("Requesting administrator privileges...")
        run_as_admin()
        return

    if command == "block":
        sites = load_config()
        block_sites(sites)
        apps = load_blocked_apps()
        killed = kill_blocked_apps(apps)
        if killed:
            print(f"Killed {killed} blocked app(s).")

    elif command == "unblock":
        unblock_sites()

    elif command == "add":
        if len(sys.argv) < 3:
            print("Usage: python blocker.py add <website>")
            return
        site = sys.argv[2].lower()
        sites = load_config()
        if site not in sites:
            sites.append(site)
            if not site.startswith("www."):
                www_site = f"www.{site}"
                if www_site not in sites:
                    sites.append(www_site)
            save_config(sites)
            print(f"Added '{site}' to block list.")
        else:
            print(f"'{site}' is already in the block list.")
        block_sites(sites)

    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: python blocker.py remove <website>")
            return
        site = sys.argv[2].lower()
        sites = load_config()
        removed = False
        if site in sites:
            sites.remove(site)
            removed = True
        www_site = f"www.{site}" if not site.startswith("www.") else site[4:]
        if www_site in sites:
            sites.remove(www_site)
            removed = True
        if removed:
            save_config(sites)
            print(f"Removed '{site}' from block list.")
        else:
            print(f"'{site}' was not in the block list.")
        block_sites(sites)

    elif command == "addapp":
        if len(sys.argv) < 3:
            print("Usage: python blocker.py addapp <process_name.exe>")
            print("Tip:   python blocker.py listapps  — to see running processes")
            return
        app_name = sys.argv[2]
        apps = load_blocked_apps()
        # Case-insensitive check
        if app_name.lower() not in [a.lower() for a in apps]:
            apps.append(app_name)
            save_blocked_apps(apps)
            print(f"Added '{app_name}' to blocked apps.")
        else:
            print(f"'{app_name}' is already in the blocked apps list.")
        kill_blocked_apps(apps)

    elif command == "removeapp":
        if len(sys.argv) < 3:
            print("Usage: python blocker.py removeapp <process_name.exe>")
            return
        app_name = sys.argv[2]
        apps = load_blocked_apps()
        # Case-insensitive removal
        new_apps = [a for a in apps if a.lower() != app_name.lower()]
        if len(new_apps) < len(apps):
            save_blocked_apps(new_apps)
            print(f"Removed '{app_name}' from blocked apps.")
        else:
            print(f"'{app_name}' was not in the blocked apps list.")

    elif command == "killapps":
        apps = load_blocked_apps()
        if not apps:
            print("No apps in the block list.")
            return
        killed = kill_blocked_apps(apps)
        if killed == 0:
            print("No blocked apps are currently running.")

    elif command == "daemon":
        print("Running in daemon mode. Blocking sites + killing apps every 30 seconds.")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                sites = load_config()
                block_sites(sites)
                apps = load_blocked_apps()
                kill_blocked_apps(apps)
                time.sleep(30)
        except KeyboardInterrupt:
            print("\nDaemon stopped.")

    else:
        print(f"Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
