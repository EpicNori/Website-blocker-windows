"""
Website Blocker - System Tray Application
Runs in the system tray and provides a menu to block/unblock sites.
Requires: pip install pystray Pillow
"""

import json
import os
import sys
import threading

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
        # Blocking active - red background
        draw.rectangle([0, 0, 63, 63], fill=(200, 50, 50))
    else:
        # Blocking inactive - gray background
        draw.rectangle([0, 0, 63, 63], fill=(128, 128, 128))

    # Draw a "B" letter
    draw.text((22, 15), "B", fill="white")

    return img


class TrayBlocker:
    def __init__(self):
        self.is_blocking = False
        self.icon = None
        self.check_current_state()

    def check_current_state(self):
        """Check if sites are currently blocked in the hosts file."""
        content = blocker.read_hosts()
        self.is_blocking = blocker.BLOCK_MARKER_START in content

    def toggle_blocking(self, icon, item):
        """Toggle website blocking on/off."""
        if self.is_blocking:
            blocker.unblock_sites()
            self.is_blocking = False
            icon.icon = create_icon_image("gray")
            icon.notify("Websites unblocked", "Website Blocker")
        else:
            sites = blocker.load_config()
            blocker.block_sites(sites)
            self.is_blocking = True
            icon.icon = create_icon_image("red")
            icon.notify("Websites blocked", "Website Blocker")
        icon.update_menu()

    def get_status_text(self, item):
        return "Blocking: ON" if self.is_blocking else "Blocking: OFF"

    def open_config(self, icon, item):
        """Open the config file in the default text editor."""
        os.startfile(blocker.CONFIG_FILE)

    def refresh_blocks(self, icon, item):
        """Re-read config and re-apply blocks."""
        if self.is_blocking:
            sites = blocker.load_config()
            blocker.block_sites(sites)
            icon.notify("Block list refreshed", "Website Blocker")

    def quit_app(self, icon, item):
        """Quit the tray application (blocks stay active)."""
        icon.stop()

    def quit_and_unblock(self, icon, item):
        """Quit and remove all blocks."""
        blocker.unblock_sites()
        icon.stop()

    def run(self):
        """Start the system tray application."""
        color = "red" if self.is_blocking else "gray"

        menu = pystray.Menu(
            pystray.MenuItem(self.get_status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "Disable Blocking" if self.is_blocking else "Enable Blocking",
                self.toggle_blocking,
            ),
            pystray.MenuItem("Refresh Block List", self.refresh_blocks),
            pystray.MenuItem("Edit Block List", self.open_config),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit (keep blocks)", self.quit_app),
            pystray.MenuItem("Quit & Unblock", self.quit_and_unblock),
        )

        self.icon = pystray.Icon(
            "WebsiteBlocker", create_icon_image(color), "Website Blocker", menu
        )

        # Auto-block on startup
        if not self.is_blocking:
            sites = blocker.load_config()
            blocker.block_sites(sites)
            self.is_blocking = True
            self.icon.icon = create_icon_image("red")

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
