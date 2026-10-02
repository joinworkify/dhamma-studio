# Build Dhamma Studio for Windows.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "=== Dhamma Studio Windows Build ==="

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Install uv first."
    exit 1
}

if (-not (Test-Path "server.py")) {
    Write-Error "server.py was not found in the project root."
    exit 1
}

if (-not (Test-Path "static\index.html")) {
    Write-Error "static\index.html was not found."
    exit 1
}

Write-Host "`n[1/5] Fetching bundled FFmpeg..."
& "$PSScriptRoot\fetch_ffmpeg_windows.ps1"

Write-Host "`n[2/5] Syncing Python dependencies..."
uv sync --group build

Write-Host "`n[3/5] Cleaning previous build..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist

Write-Host "`n[4/5] Running PyInstaller..."
uv run pyinstaller dhamma_studio.spec --noconfirm --clean

$exePath = Join-Path (Get-Location) "dist\DhammaStudio\DhammaStudio.exe"

Write-Host "`n[5/5] Checking build output..."
if (Test-Path $exePath) {
    Write-Host ""
    Write-Host "BUILD SUCCESSFUL" -ForegroundColor Green
    Write-Host "EXE: $exePath"
    Write-Host ""
    Write-Host "Distribute the entire dist\DhammaStudio folder."
} else {
    Write-Error "Build completed, but DhammaStudio.exe was not found."
    exit 1
}
