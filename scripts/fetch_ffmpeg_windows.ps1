# Downloads a static ffmpeg.exe (GPL build, includes libx264) for bundling
# into the Windows .exe via PyInstaller. Source: BtbN/FFmpeg-Builds on GitHub.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$destDir = "vendor\ffmpeg\windows"
$destBin = Join-Path $destDir "ffmpeg.exe"

if (Test-Path $destBin) {
    Write-Host "ffmpeg already present at $destBin, skipping download."
    exit 0
}

New-Item -ItemType Directory -Force -Path $destDir | Out-Null

Write-Host "Looking up latest static ffmpeg build (BtbN/FFmpeg-Builds)..."
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
$asset = $release.assets | Where-Object { $_.name -match "win64-gpl\.zip$" -and $_.name -notmatch "shared" } | Select-Object -First 1

if (-not $asset) {
    Write-Error "Could not find a win64-gpl static build asset in the latest release."
    exit 1
}

$tmpZip = Join-Path $env:TEMP "ffmpeg-windows.zip"
$tmpDir = Join-Path $env:TEMP "ffmpeg-windows-extract"

Write-Host "Downloading $($asset.name)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmpZip

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $tmpDir
Expand-Archive -Path $tmpZip -DestinationPath $tmpDir

$exe = Get-ChildItem -Path $tmpDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if (-not $exe) {
    Write-Error "ffmpeg.exe not found inside downloaded archive."
    exit 1
}
Copy-Item $exe.FullName $destBin

Remove-Item -Force $tmpZip
Remove-Item -Recurse -Force $tmpDir

Write-Host "ffmpeg downloaded to $destBin"
& $destBin -version | Select-Object -First 1
