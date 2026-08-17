$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Missing .venv. Create it with: py -3.13 -m venv .venv"
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

& $python -m pip install --upgrade pip
& $python -m pip install --editable ".[dev]"
& $python -m PyInstaller --noconfirm --clean CrashJarvis.spec

$releaseRoot = Join-Path $projectRoot "dist\CrashJarvis"

foreach ($directory in @("models", "sandbox", "logs", "captures")) {
    $source = Join-Path $projectRoot $directory
    $destination = Join-Path $releaseRoot $directory

    if (Test-Path $source) {
        Copy-Item $source $destination -Recurse -Force
    } else {
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
    }
}

Copy-Item "README.md", "LICENSE", "BUILDING.md" $releaseRoot -Force

$launcher = @'
@echo off
cd /d "%~dp0"
CrashJarvis.exe
if errorlevel 1 pause
'@
Set-Content -Path (Join-Path $releaseRoot "Start CrashJarvis.bat") -Value $launcher -Encoding ascii

$archive = Join-Path $projectRoot "dist\CrashJarvis-v0.1.0-windows-x64.zip"
if (Test-Path $archive) {
    Remove-Item $archive -Force
}

Compress-Archive -Path "$releaseRoot\*" -DestinationPath $archive -CompressionLevel Optimal

Write-Host ""
Write-Host "Build completed: $releaseRoot"
Write-Host "Archive created: $archive"
