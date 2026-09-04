$ErrorActionPreference = "Stop"

Write-Host "=== MAGCLIP Windows Build ==="

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    py -m venv .venv
}

Write-Host "Activating virtual environment..."
& .\.venv\Scripts\Activate.ps1

Write-Host "Installing runtime dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "Installing PyInstaller..."
python -m pip install "pyinstaller>=6.10,<7"

Write-Host "Cleaning previous build output..."
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
if (Test-Path "MAGCLIP.spec") { Remove-Item "MAGCLIP.spec" -Force }

Write-Host "Building MAGCLIP.exe..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "MAGCLIP" `
    --collect-all PySide6 `
    --hidden-import keyboard `
    --hidden-import pyperclip `
    run.py

Write-Host ""
Write-Host "Build complete."
Write-Host "EXE: $((Resolve-Path '.\dist\MAGCLIP.exe').Path)"
