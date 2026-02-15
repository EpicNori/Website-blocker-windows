# Website & App Blocker for Windows

A simple productivity tool that blocks distracting websites (TikTok, YouTube, Instagram, etc.) **and kills distracting apps** on your Windows PC. Websites are blocked via the Windows `hosts` file; apps are blocked by automatically killing their processes. Runs at startup so everything stays blocked.

## Quick Start

1. Make sure [Python](https://www.python.org/downloads/) is installed (check "Add Python to PATH" during install)
2. **Right-click `install.bat` and select "Run as administrator"**
3. Done — sites are blocked, apps get killed, and it auto-starts on every login

## How It Works

- **Websites**: Adds entries to `C:\Windows\System32\drivers\etc\hosts` that redirect blocked domains to `127.0.0.1`, so your browser can't reach them.
- **Apps**: Scans running processes every 30 seconds and force-kills any that match your blocked apps list (using `taskkill`).
- **Autostart**: Uses Windows Task Scheduler to launch the daemon at login with admin rights — no UAC prompt on boot.
- A background daemon re-applies everything every 30 seconds so you can't easily bypass it.
- The installer blocks sites, kills apps, sets up autostart, **and starts the daemon immediately** so there's no gap.

## Files

| File | Description |
|------|-------------|
| `blocker.py` | Core blocker — handles both websites and apps |
| `blocked_sites.json` | Config file — lists blocked sites AND apps (edit this!) |
| `setup_autostart.py` | Adds/removes the blocker from Windows startup |
| `tray_blocker.py` | System tray app with toggle controls |
| `install.bat` | One-click install (block + autostart) |
| `uninstall.bat` | One-click uninstall (unblock + remove autostart) |

## Usage

### Edit the block list

Open `blocked_sites.json` in any text editor:

```json
{
  "blocked_sites": [
    "www.tiktok.com",
    "tiktok.com",
    "www.youtube.com",
    "youtube.com"
  ],
  "blocked_apps": [
    "TikTok.exe",
    "Instagram.exe"
  ]
}
```

### Website commands

```
python blocker.py block           # Block all sites + kill blocked apps
python blocker.py unblock         # Unblock all sites
python blocker.py add tiktok.com  # Add a site (auto-adds www. variant)
python blocker.py remove tiktok.com
python blocker.py status          # Show what's blocked
python blocker.py list            # Show full config
```

### App commands

```
python blocker.py addapp TikTok.exe      # Add an app to the block list
python blocker.py removeapp TikTok.exe   # Remove an app
python blocker.py killapps               # Kill all blocked apps right now
python blocker.py listapps               # Show all running processes
```

**Tip**: Don't know the process name? Run `python blocker.py listapps` to see all running `.exe` names, then use that name with `addapp`.

### Daemon mode

```
python blocker.py daemon   # Blocks sites + kills apps every 30 seconds
python blocker.py stop     # Stop the running daemon
```

The daemon is started automatically by the installer and on every login.

### System tray app (optional)

For a tray icon with right-click controls (toggle sites, toggle apps, kill now):

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
- Administrator privileges (needed to edit the hosts file and kill processes)
- `pystray` and `Pillow` (only for the tray app — installed automatically by `install.bat`)
