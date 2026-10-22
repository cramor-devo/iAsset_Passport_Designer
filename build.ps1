# Bouwt één enkel exe-bestand (dist\iAsset_Passport_Designer.exe). / Builds a single-file exe.
# Gebruik / Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name iAsset_Passport_Designer `
    --add-data "passport_designer\data;passport_designer\data" `
    main.py
Write-Host "Klaar / Done: $PSScriptRoot\dist\iAsset_Passport_Designer.exe"
