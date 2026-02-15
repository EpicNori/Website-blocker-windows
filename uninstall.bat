@echo off
echo ============================================
echo   Website ^& App Blocker - Uninstall
echo ============================================
echo.

echo [1/2] Unblocking all websites...
python "%~dp0blocker.py" unblock
echo.

echo [2/2] Removing from Windows startup...
python "%~dp0setup_autostart.py" uninstall
echo.

echo ============================================
echo   Uninstall complete!
echo ============================================
echo All websites have been unblocked, app blocking
echo has been stopped, and the blocker has been
echo removed from startup.
echo.
pause
