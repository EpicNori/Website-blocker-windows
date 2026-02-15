@echo off
echo ============================================
echo   Website ^& App Blocker - Installation
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies...
pip install pystray Pillow
echo.

echo [2/3] Blocking websites and killing blocked apps...
python "%~dp0blocker.py" block
echo.

echo [3/3] Adding to Windows startup...
python "%~dp0setup_autostart.py" install
echo.

echo ============================================
echo   Installation complete!
echo ============================================
echo.
echo Your websites are now blocked and blocked apps
echo will be killed automatically every 30 seconds.
echo The blocker will start automatically when you log in.
echo.
echo To edit which sites/apps are blocked, edit:
echo   %~dp0blocked_sites.json
echo.
echo To see running apps (so you know the .exe name):
echo   python blocker.py listapps
echo.
echo To uninstall, run uninstall.bat
echo.
pause
