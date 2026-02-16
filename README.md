# Website & App Blocker for Windows

A productivity tool that blocks distracting websites, **specific URL paths** (like YouTube Shorts), and kills distracting apps on your Windows PC.

- **Entire domains** are blocked via the Windows `hosts` file (e.g. tiktok.com)
- **Specific URL paths** are blocked via Chrome/Edge/Brave browser policy (e.g. youtube.com/shorts)
- **Apps** are blocked by automatically killing their processes

Runs at startup so everything stays blocked.

## Quick Start

1. Make sure [Python](https://www.python.org/downloads/) is installed (check "Add Python to PATH" during install)
2. **Right-click `install.bat` and select "Run as administrator"**
3. Done — sites are blocked, apps get killed, and it auto-starts on every login

## How It Works

- **Sites** (`blocked_sites`): Adds entries to `C:\Windows\System32\drivers\etc\hosts` that redirect blocked domains to `127.0.0.1`. Blocks the entire domain.
- **URLs** (`blocked_urls`): Writes URL patterns to Chrome/Edge/Brave `URLBlocklist` browser policy via the registry. This lets you block **specific paths** (like `/shorts`) without blocking the whole site. Works with HTTPS.
- **Apps** (`blocked_apps`): Scans running processes every 30 seconds and force-kills any that match your list.
- **Autostart**: Uses Windows Task Scheduler to launch the daemon at login with admin rights — no UAC prompt on boot.
- The installer starts the daemon immediately so there's no gap.

## Files

| File | Description |
|------|-------------|
| `blocker.py` | Core blocker — handles sites, URLs, and apps |
| `blocked_sites.json` | Config file — edit this to customize what's blocked |
| `setup_autostart.py` | Adds/removes the blocker from Windows startup |
| `tray_blocker.py` | System tray app with toggle controls |
| `install.bat` | One-click install (block + autostart) |
| `uninstall.bat` | One-click uninstall (unblock + remove autostart) |

## Usage

### Edit the config file

Open `blocked_sites.json` in any text editor:

```json
{
  "blocked_sites": [
    "tiktok.com",
    "www.tiktok.com",
    "instagram.com",
    "www.instagram.com"
  ],
  "blocked_urls": [
    "youtube.com/shorts",
    "youtube.com/shorts/*"
  ],
  "blocked_apps": [
    "TikTok.exe",
    "Instagram.exe"
  ]
}
```

- `blocked_sites` — blocks the **entire domain** (hosts file)
- `blocked_urls` — blocks **specific paths** only (browser policy, works in Chrome/Edge/Brave)
- `blocked_apps` — kills matching processes

### Site commands (block entire domains)

```
python blocker.py add tiktok.com       # Add a site (auto-adds www. variant)
python blocker.py remove tiktok.com    # Remove a site
```

### URL commands (block specific paths)

```
python blocker.py addurl youtube.com/shorts       # Block YouTube Shorts
python blocker.py addurl reddit.com/r/funny       # Block a specific subreddit
python blocker.py removeurl youtube.com/shorts     # Unblock it
```

**How it works**: `addurl` automatically adds both the exact path and a wildcard variant (`/shorts/*`) so all sub-pages are blocked too. This uses the Chrome/Edge/Brave URLBlocklist policy — no extensions needed.

**Important**: If a domain is in BOTH `blocked_sites` and `blocked_urls`, the hosts file blocks everything. To only block specific paths (like `/shorts`), make sure the domain is **only** in `blocked_urls`, not in `blocked_sites`.

### App commands

```
python blocker.py addapp TikTok.exe      # Add an app to block
python blocker.py removeapp TikTok.exe   # Remove an app
python blocker.py killapps               # Kill blocked apps now
python blocker.py listapps               # Show all running processes
```

**Tip**: Run `python blocker.py listapps` to see all running `.exe` names.

### General commands

```
python blocker.py block     # Apply all blocks now
python blocker.py unblock   # Remove all blocks
python blocker.py status    # Show what's currently blocked
python blocker.py list      # Show full config
python blocker.py daemon    # Run in background (every 30s)
python blocker.py stop      # Stop the daemon
```

### System tray app (optional)

For a tray icon with right-click controls:

```
pip install pystray Pillow
python tray_blocker.py
```

### Autostart management

```
python setup_autostart.py install    # Add to startup
python setup_autostart.py uninstall  # Remove from startup
python setup_autostart.py status     # Check status
```

## Uninstall

Run `uninstall.bat` as administrator, or manually:

```
python blocker.py stop
python blocker.py unblock
python setup_autostart.py uninstall
```

## Requirements

- Windows 10/11
- Python 3.7+
- Administrator privileges (needed to edit the hosts file, registry, and kill processes)
- Chrome, Edge, or Brave (for URL path blocking — uses browser policy)
- `pystray` and `Pillow` (only for the tray app — installed automatically by `install.bat`)
