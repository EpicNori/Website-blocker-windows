# Website Blocker for Windows

A simple productivity tool that blocks distracting websites (TikTok, YouTube, Instagram, etc.) on your Windows PC. It modifies the Windows `hosts` file to redirect blocked domains to `127.0.0.1` and registers itself in Windows autostart so it runs every time you log in.

## Quick Start

1. Make sure [Python](https://www.python.org/downloads/) is installed (check "Add Python to PATH" during install)
2. **Right-click `install.bat` and select "Run as administrator"**
3. Done — sites are blocked and the blocker will start on every login

## How It Works

The script adds entries to `C:\Windows\System32\drivers\etc\hosts` that redirect blocked domains to `127.0.0.1`. This means your browser can't reach those sites. A background daemon re-applies the blocks every 60 seconds in case anything resets them.

## Files

| File | Description |
|------|-------------|
| `blocker.py` | Core blocker — reads/writes the hosts file |
| `blocked_sites.json` | List of websites to block (edit this!) |
| `setup_autostart.py` | Adds/removes the blocker from Windows startup |
| `tray_blocker.py` | System tray app with a menu to toggle blocking |
| `install.bat` | One-click install (block + autostart) |
| `uninstall.bat` | One-click uninstall (unblock + remove autostart) |

## Usage

### Edit the block list

Open `blocked_sites.json` in any text editor and add or remove domains:

```json
{
  "blocked_sites": [
    "www.tiktok.com",
    "tiktok.com",
    "www.youtube.com",
    "youtube.com"
  ]
}
```

Or use the command line:

```
python blocker.py add snapchat.com
python blocker.py remove youtube.com
```

### Manual commands

```
python blocker.py block       # Block all sites in config
python blocker.py unblock     # Unblock all sites
python blocker.py status      # Show what's blocked
python blocker.py list        # Show the config
python blocker.py daemon      # Run in background, re-apply every 60s
```

### System tray app (optional)

For a tray icon that lets you toggle blocking with a click:

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
python blocker.py unblock
python setup_autostart.py uninstall
```

## Requirements

- Windows 10/11
- Python 3.7+
- Administrator privileges (needed to edit the hosts file)
- `pystray` and `Pillow` (only for the tray app — installed automatically by `install.bat`)
