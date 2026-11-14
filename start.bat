
@echo off
setlocal

cd /d "%~dp0"

set "PATH=%~dp0runtime\windows\x64;%PATH%"

echo Checking Pillow RAQM support...

uv run python -c "from PIL import features; print('RAQM:', features.check_feature('raqm'))"

if errorlevel 1 (
    echo Failed to check Pillow.
    pause
    exit /b 1
)

echo.
echo Starting Dhamma Studio...

uv run python server.py

pause
