"""
Website & App Blocker for Windows
Blocks distracting websites via the hosts file, specific URL paths via
browser policy (Chrome/Edge/Brave), and kills blocked apps.
Runs at startup and keeps everything blocked.
"""

import ctypes
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Fix for pythonw.exe: stdout/stderr are None when there's no console.
# Redirect to a log file so print() doesn't crash the daemon.
# ---------------------------------------------------------------------------
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocker.log")

if sys.stdout is None:
    sys.stdout = open(LOG_FILE, "a", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(LOG_FILE, "a", encoding="utf-8")

SYSTEM_HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
HOSTS_PATH = SYSTEM_HOSTS_PATH
BLOCK_MARKER_START = "# === WEBSITE BLOCKER START ==="
BLOCK_MARKER_END = "# === WEBSITE BLOCKER END ==="
REDIRECT_IP = "127.0.0.1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "blocked_sites.json")
LOCK_FILE = os.path.join(SCRIPT_DIR, "blocker.lock")
HOSTS_LIST_DIR = os.path.join(SCRIPT_DIR, "hosts")
HOSTS_CACHE_DIR = os.path.join(HOSTS_LIST_DIR, "cache")
MAX_HOSTS_DOWNLOAD_BYTES = 25 * 1024 * 1024

DEFAULT_HOSTS_SOURCES = [
    {
        "name": "PornAway porn sites",
        "url": "https://raw.githubusercontent.com/mhxion/pornaway/master/hosts/porn_sites.txt",
        "enabled": True,
    }
]

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
        "hosts_sources": DEFAULT_HOSTS_SOURCES,
    }


def load_full_config():
    """Load the full config dict, creating defaults if needed."""
    if not os.path.exists(CONFIG_FILE):
        defaults = _default_config()
        _write_config(defaults)
        return defaults

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ensure all keys exist (for configs from older versions)
    changed = False
    defaults = _default_config()
    for key in ("blocked_sites", "blocked_urls", "blocked_apps", "hosts_sources"):
        if key not in data:
            data[key] = defaults[key]
            changed = True
    if changed:
        _write_config(data)

    return data


def _write_config(data):
    """Write the full config dict atomically."""
    config_dir = os.path.dirname(os.path.abspath(CONFIG_FILE))
    os.makedirs(config_dir, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".blocker-config-", dir=config_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(temp_path, CONFIG_FILE)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def save_full_config(data):
    """Persist a complete configuration while ensuring all supported keys exist."""
    defaults = _default_config()
    normalized = {}
    for key in ("blocked_sites", "blocked_urls", "blocked_apps", "hosts_sources"):
        value = data.get(key, defaults[key]) if isinstance(data, dict) else defaults[key]
        normalized[key] = value if isinstance(value, list) else defaults[key]
    _write_config(normalized)


def load_config():
    """Load user-configured websites (without cached hosts lists)."""
    return load_full_config().get("blocked_sites", [])


def load_blocked_domains():
    """Load, normalize, and de-duplicate custom sites plus cached hosts lists."""
    domains = list(load_config())
    if os.path.isdir(HOSTS_LIST_DIR):
        for name in sorted(os.listdir(HOSTS_LIST_DIR)):
            if not name.lower().endswith((".txt", ".hosts")):
                continue
            path = os.path.join(HOSTS_LIST_DIR, name)
            if os.path.isfile(path):
                domains.extend(load_hosts_file(path))
    for source in load_full_config().get("hosts_sources", []):
        if not isinstance(source, dict) or not source.get("enabled", True):
            continue
        try:
            cache_path = _source_cache_path(source)
        except (KeyError, TypeError):
            continue
        if os.path.isfile(cache_path):
            domains.extend(load_hosts_file(cache_path))
    return sorted(set(filter(None, (normalize_domain(value) for value in domains))))


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

def normalize_domain(value):
    """Return a safe ASCII hostname, or None for invalid/non-domain input."""
    if not isinstance(value, str):
        return None
    value = value.strip().lower().rstrip(".")
    if not value:
        return None

    if "://" in value:
        value = urllib.parse.urlsplit(value).hostname or ""
    value = value.lstrip("*.").rstrip(".")
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError:
        return None

    if value == "localhost" or len(value) > 253 or "." not in value:
        return None
    try:
        ipaddress.ip_address(value)
        return None
    except ValueError:
        pass

    labels = value.split(".")
    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not re.match(r"^[a-z0-9-]+$", label)
        for label in labels
    ):
        return None
    return value


def parse_hosts_content(content):
    """Parse both plain domain lists and standard hosts-file formatted lists."""
    domains = set()
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        candidates = fields
        try:
            ipaddress.ip_address(fields[0])
            candidates = fields[1:]
        except ValueError:
            pass
        for candidate in candidates:
            domain = normalize_domain(candidate)
            if domain:
                domains.add(domain)
    return sorted(domains)


def normalize_process_name(value):
    """Return a safe executable filename or None; taskkill wildcards are forbidden."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value.lower().endswith(".exe"):
        value += ".exe"
    if len(value) > 255 or not re.match(r"^[a-zA-Z0-9_. -]+\.exe$", value):
        return None
    return value


def load_hosts_file(path):
    """Load domains from a local hosts list without failing the blocker."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as handle:
            return parse_hosts_content(handle.read())
    except OSError as exc:
        print(f"Could not read hosts list '{path}': {exc}")
        return []


def _source_cache_path(source):
    """Return a deterministic, traversal-safe cache path for a source."""
    name = re.sub(r"[^a-z0-9]+", "-", str(source.get("name", "hosts-list")).lower())
    name = name.strip("-")[:60] or "hosts-list"
    digest = hashlib.sha256(source["url"].encode("utf-8")).hexdigest()[:8]
    return os.path.join(HOSTS_CACHE_DIR, f"{name}-{digest}.txt")


def update_hosts_sources():
    """Download enabled HTTPS hosts sources, validate them, and atomically cache them."""
    sources = load_full_config().get("hosts_sources", [])
    enabled = [
        source for source in sources
        if isinstance(source, dict) and source.get("enabled", True) and source.get("url")
    ]
    if not enabled:
        print("No enabled hosts sources configured.")
        return 0

    os.makedirs(HOSTS_CACHE_DIR, exist_ok=True)
    updated = 0
    for source in enabled:
        url = str(source.get("url", ""))
        if urllib.parse.urlsplit(url).scheme.lower() != "https":
            print(f"Skipped '{source.get('name', url)}': only HTTPS sources are allowed.")
            continue
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "WebsiteBlocker/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                if urllib.parse.urlsplit(response.geturl()).scheme.lower() != "https":
                    raise ValueError("source redirected to a non-HTTPS URL")
                payload = response.read(MAX_HOSTS_DOWNLOAD_BYTES + 1)
            if len(payload) > MAX_HOSTS_DOWNLOAD_BYTES:
                raise ValueError("download exceeds 25 MB limit")
            domains = parse_hosts_content(payload.decode("utf-8-sig", errors="ignore"))
            if not domains:
                raise ValueError("source did not contain valid domains")

            cache_path = _source_cache_path(source)
            fd, temp_path = tempfile.mkstemp(prefix=".hosts-", dir=HOSTS_CACHE_DIR, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write("\n".join(domains) + "\n")
                os.replace(temp_path, cache_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            print(f"Updated '{source.get('name', url)}': {len(domains)} domains.")
            updated += 1
        except Exception as exc:
            print(f"Could not update '{source.get('name', url)}': {exc}")
    return updated

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


def read_hosts():
    """Read the current hosts file content."""
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8-sig", errors="ignore") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _write_hosts(content):
    """Write the Windows hosts file only when its content changed."""
    current = read_hosts()
    normalized = content.rstrip("\r\n") + "\r\n"
    if current.replace("\r\n", "\n") == normalized.replace("\r\n", "\n"):
        return False
    backup_path = HOSTS_PATH + ".website-blocker-backup"
    if os.path.exists(HOSTS_PATH) and not os.path.exists(backup_path):
        shutil.copy2(HOSTS_PATH, backup_path)
    with open(HOSTS_PATH, "w", encoding="utf-8", newline="") as handle:
        handle.write(normalized)
    return True


def verify_blocked_domains(domains, attempts=5, retry_delay=0.2):
    """Verify through Winsock that representative blocked domains resolve locally."""
    normalized = sorted(set(filter(None, (normalize_domain(domain) for domain in domains))))
    configured = [normalize_domain(domain) for domain in load_config()]
    samples = [domain for domain in configured if domain in normalized][:5]
    if not samples:
        samples = normalized[:5]
    if not samples:
        return []

    failures = {}
    for attempt in range(max(1, attempts)):
        failures = {}
        for domain in samples:
            try:
                addresses = {
                    result[4][0]
                    for result in socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)
                }
            except OSError as exc:
                failures[domain] = {f"error: {exc}"}
                continue
            public_addresses = addresses.difference({REDIRECT_IP, "::1"})
            if public_addresses or not addresses:
                failures[domain] = public_addresses or addresses
        if not failures:
            print(f"Verified local DNS blocking for {len(samples)} representative domain(s).")
            return samples
        if attempt + 1 < max(1, attempts):
            time.sleep(retry_delay)

    details = "; ".join(
        f"{domain} -> {', '.join(sorted(addresses))}" for domain, addresses in failures.items()
    )
    raise RuntimeError(f"Hosts entries were written but DNS blocking verification failed: {details}")


def block_sites(sites):
    """Replace the managed hosts section and flush DNS when it changed."""
    content = read_hosts()
    if content.count(BLOCK_MARKER_START) != content.count(BLOCK_MARKER_END):
        raise RuntimeError(
            "The hosts file contains an incomplete Website Blocker marker section; "
            "repair it manually before applying blocks."
        )
    content = remove_blocker_entries(content)

    domains = sorted(set(filter(None, (normalize_domain(site) for site in sites))))

    block_lines = [BLOCK_MARKER_START]
    for site in domains:
        block_lines.append(f"{REDIRECT_IP} {site}")
    block_lines.append(BLOCK_MARKER_END)

    prefix = content.rstrip("\r\n")
    new_content = (prefix + "\n\n" if prefix else "") + "\n".join(block_lines)
    if _write_hosts(new_content):
        flush_dns()
    if os.path.normcase(os.path.abspath(HOSTS_PATH)) == os.path.normcase(SYSTEM_HOSTS_PATH):
        verify_blocked_domains(domains)
    print(f"Blocked {len(domains)} domains via the Windows hosts file.")


def unblock_sites():
    """Remove all blocker entries from the hosts file."""
    content = read_hosts()
    if content.count(BLOCK_MARKER_START) != content.count(BLOCK_MARKER_END):
        raise RuntimeError(
            "The hosts file contains an incomplete Website Blocker marker section; "
            "nothing was changed."
        )
    new_content = remove_blocker_entries(content)

    if _write_hosts(new_content):
        flush_dns()
    print("All sites unblocked.")


def remove_blocker_entries(content):
    """Remove the blocker section from hosts file content."""
    lines = content.splitlines()
    new_lines = []
    inside_block = False
    pending_block = []

    for line in lines:
        if line.strip() == BLOCK_MARKER_START:
            inside_block = True
            pending_block = [line]
            continue
        if inside_block and line.strip() == BLOCK_MARKER_END:
            inside_block = False
            pending_block = []
            continue
        if inside_block:
            pending_block.append(line)
        else:
            new_lines.append(line)

    # Preserve an unterminated marker block to avoid deleting unrelated entries.
    if inside_block:
        new_lines.extend(pending_block)

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
        safe_app = normalize_process_name(app)
        if safe_app and safe_app.lower() in running:
            try:
                subprocess.call(
                    ["taskkill", "/F", "/IM", safe_app],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                print(f"Killed blocked app: {safe_app}")
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
        print(f"Blocked domains via hosts file: {len(blocked)}")
        for site in blocked[:25]:
            print(f"  - {site}")
        if len(blocked) > 25:
            print(f"  ... and {len(blocked) - 25} more")
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
    print("  python blocker.py updatehosts   - Download configured hosts lists")
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
        print("\nHosts-list sources:")
        for source in config.get("hosts_sources", []):
            if not isinstance(source, dict):
                print("  - invalid source entry (ignored)")
                continue
            state = "enabled" if source.get("enabled", True) else "disabled"
            print(f"  - {source.get('name', source.get('url', 'unnamed'))} ({state})")
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

    if command == "updatehosts":
        update_hosts_sources()
        return

    # --- Commands that need admin ---

    if not is_admin():
        print("Requesting administrator privileges...")
        run_as_admin()
        return

    if command == "block":
        block_sites(load_blocked_domains())
        urls = load_blocked_urls()
        apply_url_blocks(urls)
        apps = load_blocked_apps()
        killed = kill_blocked_apps(apps)
        if killed:
            print(f"Killed {killed} blocked app(s).")

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
        block_sites(load_blocked_domains())

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
        block_sites(load_blocked_domains())

    elif command == "addapp":
        if len(sys.argv) < 3:
            print("Usage: python blocker.py addapp <process_name.exe>")
            print("Tip:   python blocker.py listapps  — to see running processes")
            return
        app_name = normalize_process_name(sys.argv[2])
        if not app_name:
            print("Invalid process name. Wildcards and paths are not allowed.")
            return
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
                    sites = load_blocked_domains()
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
