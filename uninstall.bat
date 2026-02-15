@echo off
echo ============================================
echo   Website ^& App Blocker - Uninstall
echo ============================================
echo.

echo [1/3] Stopping running daemon...
python "%~dp0blocker.py" stop 2>nul
echo.

echo [2/3] Unblocking all websites...
python "%~dp0blocker.py" unblock
echo.

echo [3/3] Removing from Windows startup...
python "%~dp0setup_autostart.py" uninstall
echo.

:: Clean up lock file if it exists
if exist "%~dp0blocker.lock" del "%~dp0blocker.lock"

echo ============================================
echo   Uninstall complete!
echo ============================================
echo All websites have been unblocked, app blocking
echo has been stopped, and the blocker has been
echo removed from startup.
echo.
pause
