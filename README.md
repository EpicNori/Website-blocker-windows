# Website & App Blocker for Windows

A productivity tool that blocks distracting websites, **specific URL paths** (like YouTube Shorts), and kills distracting apps on your Windows PC.

- **Entire domains** are blocked via the Windows `hosts` file (e.g. tiktok.com)
- **Large hosts lists** in standard `127.0.0.1 domain.example` format are supported (including PornAway-style lists)
- **Specific URL paths** are blocked via Chrome/Edge/Brave browser policy (e.g. youtube.com/shorts)
- **Apps** are blocked by automatically killing their processes

Runs at startup so everything stays blocked.

## Quick Start

1. Make sure [Python](https://www.python.org/downloads/) is installed (check "Add Python to PATH" during install)
2. **Right-click `install.bat` and select "Run as administrator"**
3. Done — sites are blocked, apps get killed, and the desktop control panel opens

After installation, double-click `start_ui.bat` whenever you want to open the control panel. Windows requests administrator privileges because editing the hosts file requires them; the UI will not open in a non-functional, non-administrator mode.

## How It Works

- **Sites** (`blocked_sites`): Adds a clearly marked, replaceable section to `C:\Windows\System32\drivers\etc\hosts` that redirects blocked domains to `127.0.0.1`.
- **Live verification**: After applying the hosts section, the blocker checks representative configured domains through Windows Winsock. It reports an error instead of a false success if any still resolve publicly.
- **Hosts sources** (`hosts_sources`): Downloads configured HTTPS lists into `hosts/cache/`. Cached domains and local `.txt`/`.hosts` files placed directly in `hosts/` are merged with `blocked_sites`, normalized, and de-duplicated.
- **URLs** (`blocked_urls`): Writes URL patterns to Chrome/Edge/Brave `URLBlocklist` browser policy via the registry. This lets you block **specific paths** (like `/shorts`) without blocking the whole site. Works with HTTPS.
- **Apps** (`blocked_apps`): Scans running processes every 30 seconds and force-kills any that match your list.
- **Autostart**: Uses Windows Task Scheduler to launch the daemon at login with admin rights — no UAC prompt on boot.
- The installer starts the daemon immediately so there's no gap.

## Files

| File | Description |
|------|-------------|
| `blocker.py` | Core blocker — handles sites, URLs, and apps |
| `blocker_ui.py` | Native Windows control panel built with Tkinter |
| `blocked_sites.json` | Config file — edit this to customize what's blocked |
| `setup_autostart.py` | Adds/removes the blocker from Windows startup |
| `tray_blocker.py` | System tray app with toggle controls |
| `start_ui.bat` | Opens the desktop control panel |
| `install.bat` | One-click install (block + autostart) |
| `uninstall.bat` | One-click uninstall (unblock + remove autostart) |

## Usage

### Desktop control panel

Double-click `start_ui.bat`. The interface provides tabs for:

- websites and URL-path rules
- blocked Windows applications
- external HTTPS hosts-list sources
- update and activity logs

Use **Enable Blocking** to write the managed section to the Windows hosts file. **Remove Blocking** removes only the managed section and leaves unrelated hosts entries intact.

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
  ],
  "hosts_sources": [
    {
      "name": "PornAway porn sites",
      "url": "https://raw.githubusercontent.com/mhxion/pornaway/master/hosts/porn_sites.txt",
      "enabled": true
    }
  ]
}
```

- `blocked_sites` — blocks the **entire domain** (hosts file)
- `blocked_urls` — blocks **specific paths** only (browser policy, works in Chrome/Edge/Brave)
- `blocked_apps` — kills matching processes
- `hosts_sources` — HTTPS hosts lists downloaded with `python blocker.py updatehosts`

The included PornAway source is compatible with the linked project, but its own metadata says the list was last updated in 2018. You can disable it or replace the URL with a maintained source.

### Site commands (block entire domains)

```
python blocker.py add tiktok.com       # Add a site (auto-adds www. variant)
python blocker.py remove tiktok.com    # Remove a site
python blocker.py updatehosts          # Refresh configured external hosts lists
```

You can also place a local PornAway-style list directly in `hosts/`, for example:

```text
127.0.0.1 example.com
0.0.0.0 ads.example.net
plain-domain.example
```

Only valid domains are imported. Comments, localhost entries, IP addresses, invalid hostnames, and duplicates are ignored. A first-run backup is stored beside the Windows hosts file as `hosts.website-blocker-backup`.

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
