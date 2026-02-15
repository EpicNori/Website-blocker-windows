"""
Website Blocker for Windows
Blocks distracting websites by adding entries to the Windows hosts file.
Runs at startup and keeps websites blocked.
"""

import ctypes
import json
import os
import sys
import time

HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
BLOCK_MARKER_START = "# === WEBSITE BLOCKER START ==="
BLOCK_MARKER_END = "# === WEBSITE BLOCKER END ==="
REDIRECT_IP = "127.0.0.1"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocked_sites.json")


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


def load_config():
    """Load the list of blocked websites from the config file."""
    if not os.path.exists(CONFIG_FILE):
        # Create default config if it doesn't exist
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
        save_config(default_sites)
        return default_sites

    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    return data.get("blocked_sites", [])


def save_config(sites):
    """Save the list of blocked websites to the config file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"blocked_sites": sites}, f, indent=2)


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

    # Remove any existing blocker entries first
    content = remove_blocker_entries(content)

    # Build the block entries
    block_lines = [BLOCK_MARKER_START]
    for site in sites:
        block_lines.append(f"{REDIRECT_IP} {site}")
    block_lines.append(BLOCK_MARKER_END)

    # Append to hosts file
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


def show_status():
    """Show which sites are currently blocked."""
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

    print(f"\nConfig file: {CONFIG_FILE}")


def print_usage():
    """Print usage information."""
    print("Website Blocker for Windows")
    print("-" * 40)
    print("Usage:")
    print("  python blocker.py block     - Block all sites from config")
    print("  python blocker.py unblock   - Unblock all sites")
    print("  python blocker.py status    - Show blocked sites")
    print("  python blocker.py add <site> - Add a site to the block list")
    print("  python blocker.py remove <site> - Remove a site from the block list")
    print("  python blocker.py list      - List sites in config")
    print("  python blocker.py daemon    - Run in background, re-apply blocks periodically")


def main():
    # If no arguments, default to blocking
    if len(sys.argv) < 2:
        command = "block"
    else:
        command = sys.argv[1].lower()

    # Commands that don't need admin
    if command == "list":
        sites = load_config()
        print("Sites in block list:")
        for site in sites:
            print(f"  - {site}")
        return

    if command == "status":
        show_status()
        return

    if command == "help":
        print_usage()
        return

    # Commands that need admin
    if not is_admin():
        print("Requesting administrator privileges...")
        run_as_admin()
        return

    if command == "block":
        sites = load_config()
        block_sites(sites)

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
            # Also add www. variant if not present
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

    elif command == "daemon":
        print("Running in daemon mode. Blocks will be re-applied every 60 seconds.")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                sites = load_config()
                block_sites(sites)
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nDaemon stopped.")

    else:
        print(f"Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
