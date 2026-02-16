"""
Website & App Blocker - System Tray Application
Runs in the system tray and provides a menu to block/unblock sites and kill apps.
Requires: pip install pystray Pillow
"""

import os
import sys
import threading
import time

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    print("Missing dependencies. Install them with:")
    print("  pip install pystray Pillow")
    sys.exit(1)

# Import the blocker module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blocker


def create_icon_image(color="red"):
    """Create a simple colored icon with a 'B' for Blocker."""
    img = Image.new("RGB", 64, 64)
    draw = ImageDraw.Draw(img)

    if color == "red":
        draw.rectangle([0, 0, 63, 63], fill=(200, 50, 50))
    else:
        draw.rectangle([0, 0, 63, 63], fill=(128, 128, 128))

    draw.text((22, 15), "B", fill="white")
    return img


class TrayBlocker:
    def __init__(self):
        self.is_blocking = False
        self.app_blocking_enabled = True
        self.icon = None
        self.daemon_thread = None
        self.daemon_running = False
        self.check_current_state()

    def check_current_state(self):
        """Check if sites are currently blocked in the hosts file."""
        content = blocker.read_hosts()
        self.is_blocking = blocker.BLOCK_MARKER_START in content

    def start_daemon(self):
        """Start the background daemon that re-applies blocks and kills apps."""
        self.daemon_running = True
        self.daemon_thread = threading.Thread(target=self._daemon_loop, daemon=True)
        self.daemon_thread.start()

    def _daemon_loop(self):
        """Background loop: re-apply site blocks, URL blocks, and kill blocked apps."""
        while self.daemon_running:
            try:
                if self.is_blocking:
                    sites = blocker.load_config()
                    blocker.block_sites(sites)
                    urls = blocker.load_blocked_urls()
                    blocker.apply_url_blocks(urls)
                if self.app_blocking_enabled:
                    apps = blocker.load_blocked_apps()
                    blocker.kill_blocked_apps(apps)
            except Exception:
                pass
            time.sleep(30)

    def toggle_blocking(self, icon, item):
        """Toggle website + URL blocking on/off."""
        if self.is_blocking:
            blocker.unblock_sites()
            blocker.remove_url_blocks()
            self.is_blocking = False
            icon.icon = create_icon_image("gray")
            icon.notify("Sites & URLs unblocked", "Website & App Blocker")
        else:
            sites = blocker.load_config()
            blocker.block_sites(sites)
            urls = blocker.load_blocked_urls()
            blocker.apply_url_blocks(urls)
            self.is_blocking = True
            icon.icon = create_icon_image("red")
            icon.notify("Sites & URLs blocked", "Website & App Blocker")
        icon.update_menu()

    def toggle_app_blocking(self, icon, item):
        """Toggle app blocking on/off."""
        self.app_blocking_enabled = not self.app_blocking_enabled
        state = "enabled" if self.app_blocking_enabled else "disabled"
        icon.notify(f"App blocking {state}", "Website & App Blocker")
        icon.update_menu()

    def kill_apps_now(self, icon, item):
        """Immediately kill all blocked apps."""
        apps = blocker.load_blocked_apps()
        killed = blocker.kill_blocked_apps(apps)
        if killed:
            icon.notify(f"Killed {killed} blocked app(s)", "Website & App Blocker")
        else:
            icon.notify("No blocked apps running", "Website & App Blocker")

    def get_status_text(self, item):
        site_status = "ON" if self.is_blocking else "OFF"
        app_status = "ON" if self.app_blocking_enabled else "OFF"
        return f"Sites: {site_status} | Apps: {app_status}"

    def open_config(self, icon, item):
        """Open the config file in the default text editor."""
        os.startfile(blocker.CONFIG_FILE)

    def refresh_blocks(self, icon, item):
        """Re-read config and re-apply blocks."""
        if self.is_blocking:
            sites = blocker.load_config()
            blocker.block_sites(sites)
            urls = blocker.load_blocked_urls()
            blocker.apply_url_blocks(urls)
        if self.app_blocking_enabled:
            apps = blocker.load_blocked_apps()
            blocker.kill_blocked_apps(apps)
        icon.notify("Block list refreshed", "Website & App Blocker")

    def quit_app(self, icon, item):
        """Quit the tray application (blocks stay active)."""
        self.daemon_running = False
        icon.stop()

    def quit_and_unblock(self, icon, item):
        """Quit and remove all blocks."""
        self.daemon_running = False
        blocker.unblock_sites()
        blocker.remove_url_blocks()
        icon.stop()

    def run(self):
        """Start the system tray application."""
        color = "red" if self.is_blocking else "gray"

        menu = pystray.Menu(
            pystray.MenuItem(self.get_status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "Disable Site Blocking" if self.is_blocking else "Enable Site Blocking",
                self.toggle_blocking,
            ),
            pystray.MenuItem(
                lambda item: "Disable App Blocking" if self.app_blocking_enabled else "Enable App Blocking",
                self.toggle_app_blocking,
            ),
            pystray.MenuItem("Kill Blocked Apps Now", self.kill_apps_now),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh Block List", self.refresh_blocks),
            pystray.MenuItem("Edit Block List", self.open_config),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit (keep blocks)", self.quit_app),
            pystray.MenuItem("Quit & Unblock All", self.quit_and_unblock),
        )

        self.icon = pystray.Icon(
            "WebsiteAppBlocker", create_icon_image(color), "Website & App Blocker", menu
        )

        # Auto-block on startup
        if not self.is_blocking:
            sites = blocker.load_config()
            blocker.block_sites(sites)
            self.is_blocking = True
            self.icon.icon = create_icon_image("red")

        # Apply URL blocks and kill blocked apps immediately
        urls = blocker.load_blocked_urls()
        blocker.apply_url_blocks(urls)
        apps = blocker.load_blocked_apps()
        blocker.kill_blocked_apps(apps)

        # Start background daemon
        self.start_daemon()

        self.icon.run()


def main():
    if not blocker.is_admin():
        print("Requesting administrator privileges...")
        blocker.run_as_admin()
        return

    app = TrayBlocker()
    app.run()


if __name__ == "__main__":
    main()
