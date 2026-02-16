"""
Website & App Blocker for Windows
Blocks distracting websites via the hosts file, specific URL paths via
browser policy (Chrome/Edge/Brave), and kills blocked apps.
Runs at startup and keeps everything blocked.
"""

import ctypes
import json
import os
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Fix for pythonw.exe: stdout/stderr are None when there's no console.
# Redirect to a log file so print() doesn't crash the daemon.
# ---------------------------------------------------------------------------
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocker.log")

if sys.stdout is None:
    sys.stdout = open(LOG_FILE, "a", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(LOG_FILE, "a", encoding="utf-8")

HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
BLOCK_MARKER_START = "# === WEBSITE BLOCKER START ==="
BLOCK_MARKER_END = "# === WEBSITE BLOCKER END ==="
REDIRECT_IP = "127.0.0.1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "blocked_sites.json")
LOCK_FILE = os.path.join(SCRIPT_DIR, "blocker.lock")

# Default blocked apps — process names as they appear in Task Manager
DEFAULT_BLOCKED_APPS = [
    "TikTok.exe",
    "Instagram.exe",
]

# Browser policy registry paths for URLBlocklist
BROWSER_POLICY_KEYS = [
    r"SOFTWARE\Policies\Google\Chrome\URLBlocklist",       # Chrome
    r"SOFTWARE\Policies\Microsoft\Edge\URLBlocklist",       # Edge
    r"SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist",  # Brave
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

def _default_config():
    """Return the default config dict."""
    return {
        "blocked_sites": [
            "www.tiktok.com",
            "tiktok.com",
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
        ],
        "blocked_urls": [
            "youtube.com/shorts",
            "youtube.com/shorts/*",
            "m.youtube.com/shorts",
            "m.youtube.com/shorts/*",
        ],
        "blocked_apps": DEFAULT_BLOCKED_APPS,
    }


def load_full_config():
    """Load the full config dict, creating defaults if needed."""
    if not os.path.exists(CONFIG_FILE):
        defaults = _default_config()
        _write_config(defaults)
        return defaults

    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)

    # Ensure all keys exist (for configs from older versions)
    changed = False
    for key in ("blocked_sites", "blocked_urls", "blocked_apps"):
        if key not in data:
            data[key] = []
            changed = True
    if changed:
        _write_config(data)

    return data


def _write_config(data):
    """Write the full config dict to disk."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_config():
    """Load the list of blocked websites."""
    return load_full_config().get("blocked_sites", [])


def load_blocked_apps():
    """Load the list of blocked apps."""
    return load_full_config().get("blocked_apps", [])


def load_blocked_urls():
    """Load the list of blocked URL paths."""
    return load_full_config().get("blocked_urls", [])


def save_config(sites, apps=None):
    """Save blocked websites (and optionally apps) to the config file."""
    data = load_full_config() if os.path.exists(CONFIG_FILE) else _default_config()
    data["blocked_sites"] = sites
    if apps is not None:
        data["blocked_apps"] = apps
    _write_config(data)


def save_blocked_apps(apps):
    """Save the blocked apps list, preserving everything else."""
    data = load_full_config()
    data["blocked_apps"] = apps
    _write_config(data)


def save_blocked_urls(urls):
    """Save the blocked URLs list, preserving everything else."""
    data = load_full_config()
    data["blocked_urls"] = urls
    _write_config(data)


# ---------------------------------------------------------------------------
# Website blocking (hosts file)
# ---------------------------------------------------------------------------

BROWSERS = ["chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe"]


def flush_dns():
    """Flush the Windows DNS cache so blocked sites take effect immediately."""
    try:
        subprocess.call(
            ["ipconfig", "/flushdns"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass


def restart_browsers():
    """Gracefully close and relaunch browsers to drop cached connections.

    Uses taskkill without /F so browsers save their session. When the user
    reopens the browser it will offer to restore tabs — blocked sites will
    fail to load.
    """
    running = get_running_processes()
    closed = []

    for browser in BROWSERS:
        if browser.lower() in running:
            # Graceful close (no /F) — lets the browser save session data
            subprocess.call(
                ["taskkill", "/IM", browser],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            closed.append(browser)

    if closed:
        # Give browsers a moment to save session data
        time.sleep(2)

        # Force-kill any that didn't close gracefully
        for browser in closed:
            subprocess.call(
                ["taskkill", "/F", "/IM", browser],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

        time.sleep(1)

        # Relaunch the browsers (they will restore their previous session)
        for browser in closed:
            try:
                subprocess.Popen(
                    [browser],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    | getattr(subprocess, "DETACHED_PROCESS", 0),
                )
            except Exception:
                pass

        names = ", ".join(b.replace(".exe", "") for b in closed)
        print(f"Restarted browser(s): {names}")


def read_hosts():
    """Read the current hosts file content."""
    try:
        with open(HOSTS_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def block_sites(sites):
    """Add blocked sites to the hosts file and flush DNS."""
    content = read_hosts()
    content = remove_blocker_entries(content)

    block_lines = [BLOCK_MARKER_START]
    for site in sites:
        block_lines.append(f"{REDIRECT_IP} {site}")
    block_lines.append(BLOCK_MARKER_END)

    new_content = content.rstrip("\n") + "\n\n" + "\n".join(block_lines) + "\n"

    with open(HOSTS_PATH, "w") as f:
        f.write(new_content)

    flush_dns()
    print(f"Blocked {len(sites)} sites.")


def unblock_sites():
    """Remove all blocker entries from the hosts file."""
    content = read_hosts()
    new_content = remove_blocker_entries(content)

    with open(HOSTS_PATH, "w") as f:
        f.write(new_content)

    flush_dns()
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
# URL path blocking (browser policy via registry)
# ---------------------------------------------------------------------------

def apply_url_blocks(urls):
    """Write blocked URL patterns to Chrome/Edge/Brave URLBlocklist policy."""
    if not urls:
        return

    try:
        import winreg
    except ImportError:
        return

    for reg_path in BROWSER_POLICY_KEYS:
        try:
            # Create the key (and parent keys) if they don't exist
            key = winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ
            )

            # Clear old entries first
            try:
                i = 0
                while True:
                    name, _, _ = winreg.EnumValue(key, i)
                    try:
                        winreg.DeleteValue(key, name)
                    except OSError:
                        i += 1
            except OSError:
                pass

            # Write new entries (1-indexed)
            for idx, url in enumerate(urls, start=1):
                winreg.SetValueEx(key, str(idx), 0, winreg.REG_SZ, url)

            winreg.CloseKey(key)
        except PermissionError:
            pass
        except Exception:
            pass

    print(f"Applied {len(urls)} URL block(s) to browser policies.")


def remove_url_blocks():
    """Remove all URLBlocklist policy entries from the registry."""
    try:
        import winreg
    except ImportError:
        return

    removed_any = False
    for reg_path in BROWSER_POLICY_KEYS:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ
            )
            # Delete all values
            try:
                while True:
                    name, _, _ = winreg.EnumValue(key, 0)
                    winreg.DeleteValue(key, name)
            except OSError:
                pass
            winreg.CloseKey(key)

            # Try to remove the now-empty key
            parent_path = "\\".join(reg_path.split("\\")[:-1])
            child_name = reg_path.split("\\")[-1]
            try:
                parent = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, parent_path, 0, winreg.KEY_SET_VALUE
                )
                winreg.DeleteKey(parent, child_name)
                winreg.CloseKey(parent)
            except OSError:
                pass

            removed_any = True
        except FileNotFoundError:
            pass
        except Exception:
            pass

    if removed_any:
        print("Removed URL blocks from browser policies.")


# ---------------------------------------------------------------------------
# Daemon lock file
# ---------------------------------------------------------------------------

def write_lock_file():
    """Write the current PID to the lock file."""
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_lock_file():
    """Remove the lock file."""
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def get_daemon_pid():
    """Read the PID from the lock file. Returns None if no daemon is running."""
    if not os.path.exists(LOCK_FILE):
        return None
    try:
        with open(LOCK_FILE, "r") as f:
            pid = int(f.read().strip())
        # Check if the process is still running
        output = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if str(pid) in output.decode("utf-8", errors="ignore"):
            return pid
        # Stale lock file
        remove_lock_file()
        return None
    except Exception:
        remove_lock_file()
        return None


def stop_daemon():
    """Stop a running daemon by killing its process."""
    pid = get_daemon_pid()
    if pid is None:
        print("No daemon is currently running.")
        return False
    try:
        subprocess.call(
            ["taskkill", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        remove_lock_file()
        print(f"Stopped daemon (PID {pid}).")
        return True
    except Exception as e:
        print(f"Error stopping daemon: {e}")
        return False


# ---------------------------------------------------------------------------
# Status / display
# ---------------------------------------------------------------------------

def show_status():
    """Show which sites, URLs, and apps are currently blocked."""
    # Sites (hosts file)
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
        print("Blocked sites (entire domain via hosts file):")
        for site in blocked:
            print(f"  - {site}")
    else:
        print("No sites are currently blocked.")

    # URLs (browser policy)
    urls = load_blocked_urls()
    if urls:
        print("\nBlocked URLs (path-based via browser policy — Chrome/Edge/Brave):")
        for url in urls:
            print(f"  - {url}")
    else:
        print("\nNo URL paths are being blocked.")

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
    print("-" * 50)
    print()
    print("Site commands (blocks entire domain via hosts file):")
    print("  python blocker.py add <site>    - Add a site to block")
    print("  python blocker.py remove <site> - Remove a site")
    print()
    print("URL commands (blocks specific paths in Chrome/Edge/Brave):")
    print("  python blocker.py addurl <url>    - Add a URL path to block")
    print("  python blocker.py removeurl <url> - Remove a URL path")
    print("  Example: python blocker.py addurl youtube.com/shorts")
    print()
    print("App commands:")
    print("  python blocker.py addapp <name.exe>    - Add an app to block")
    print("  python blocker.py removeapp <name.exe> - Remove an app")
    print("  python blocker.py killapps             - Kill blocked apps now")
    print("  python blocker.py listapps             - List running processes")
    print()
    print("General:")
    print("  python blocker.py block     - Apply all blocks now")
    print("  python blocker.py unblock   - Remove all blocks")
    print("  python blocker.py status    - Show what's blocked")
    print("  python blocker.py list      - Show config")
    print("  python blocker.py daemon    - Run in background")
    print("  python blocker.py stop      - Stop the daemon")


def main():
    if len(sys.argv) < 2:
        command = "block"
    else:
        command = sys.argv[1].lower()

    # --- Commands that don't need admin ---

    if command == "list":
        config = load_full_config()
        print("Blocked sites (entire domain):")
        for site in config.get("blocked_sites", []):
            print(f"  - {site}")
        print(f"\nBlocked URLs (specific paths):")
        for url in config.get("blocked_urls", []):
            print(f"  - {url}")
        print(f"\nBlocked apps:")
        for app in config.get("blocked_apps", []):
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
        urls = load_blocked_urls()
        apply_url_blocks(urls)
        apps = load_blocked_apps()
        killed = kill_blocked_apps(apps)
        if killed:
            print(f"Killed {killed} blocked app(s).")
        # Restart browsers so already-open blocked sites get dropped
        restart_browsers()

    elif command == "unblock":
        unblock_sites()
        remove_url_blocks()

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

    elif command == "addurl":
        if len(sys.argv) < 3:
            print("Usage: python blocker.py addurl <url_pattern>")
            print()
            print("Examples:")
            print("  python blocker.py addurl youtube.com/shorts")
            print("  python blocker.py addurl youtube.com/shorts/*")
            print("  python blocker.py addurl reddit.com/r/funny")
            print()
            print("Tip: Don't include http:// — just domain/path.")
            print("     Add /* at the end to block all sub-paths.")
            return
        url_pattern = sys.argv[2]
        urls = load_blocked_urls()
        if url_pattern not in urls:
            urls.append(url_pattern)
            # Auto-add wildcard variant if not already present
            if not url_pattern.endswith("/*") and not url_pattern.endswith("*"):
                wildcard = url_pattern.rstrip("/") + "/*"
                if wildcard not in urls:
                    urls.append(wildcard)
            save_blocked_urls(urls)
            print(f"Added '{url_pattern}' to blocked URLs.")
        else:
            print(f"'{url_pattern}' is already in the blocked URLs list.")
        apply_url_blocks(urls)

    elif command == "removeurl":
        if len(sys.argv) < 3:
            print("Usage: python blocker.py removeurl <url_pattern>")
            return
        url_pattern = sys.argv[2]
        urls = load_blocked_urls()
        removed = False
        # Remove exact match and wildcard variant
        to_remove = [url_pattern]
        if not url_pattern.endswith("/*"):
            to_remove.append(url_pattern.rstrip("/") + "/*")
        new_urls = [u for u in urls if u not in to_remove]
        if len(new_urls) < len(urls):
            save_blocked_urls(new_urls)
            print(f"Removed '{url_pattern}' from blocked URLs.")
            removed = True
        if not removed:
            print(f"'{url_pattern}' was not in the blocked URLs list.")
        apply_url_blocks(new_urls)

    elif command == "killapps":
        apps = load_blocked_apps()
        if not apps:
            print("No apps in the block list.")
            return
        killed = kill_blocked_apps(apps)
        if killed == 0:
            print("No blocked apps are currently running.")

    elif command == "stop":
        stop_daemon()

    elif command == "daemon":
        # Stop any already-running daemon first
        existing_pid = get_daemon_pid()
        if existing_pid:
            print(f"Stopping existing daemon (PID {existing_pid})...")
            stop_daemon()

        write_lock_file()
        print(f"Running in daemon mode (PID {os.getpid()}).")
        print("Blocking sites + URLs + killing apps every 30 seconds.")
        try:
            while True:
                try:
                    sites = load_config()
                    block_sites(sites)
                    urls = load_blocked_urls()
                    apply_url_blocks(urls)
                    apps = load_blocked_apps()
                    kill_blocked_apps(apps)
                except Exception as e:
                    # Don't let a single iteration failure kill the daemon
                    print(f"Daemon cycle error: {e}")
                time.sleep(30)
        except KeyboardInterrupt:
            print("\nDaemon stopped.")
        finally:
            remove_lock_file()

    else:
        print(f"Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
