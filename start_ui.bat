@echo off
cd /d "%~dp0"

where pythonw.exe >nul 2>&1
if errorlevel 1 (
    python "%~dp0blocker_ui.py"
) else (
    start "" pythonw "%~dp0blocker_ui.py"
)
