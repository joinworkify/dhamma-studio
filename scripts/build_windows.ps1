# Build DhammaStudio.exe for Windows via PyInstaller + uv.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
}

Write-Host "Fetching ffmpeg for bundling..."
& "$PSScriptRoot\fetch_ffmpeg_windows.ps1"

Write-Host "Syncing dependencies (including build group)..."
uv sync --group build

Write-Host "Cleaning previous build output..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist

Write-Host "Building DhammaStudio.exe..."
uv run pyinstaller dhamma_studio.spec --noconfirm

$exePath = "dist\DhammaStudio\DhammaStudio.exe"
if (Test-Path $exePath) {
    Write-Host "Build succeeded: $exePath"
} else {
    Write-Error "Build finished but $exePath was not found."
    exit 1
}
