# Bouwt één enkel exe-bestand met de versie in de naam, bv. dist\iAsset Passport Designer v0.5.0.exe.
# Builds a single-file exe with the version in its name, e.g. dist\iAsset Passport Designer v0.5.0.exe.
# Gebruik / Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# NL: Lees de versie uit __version__ (zelfde patroon als release.yml). / EN: Read the version from __version__ (same pattern as release.yml).
$match = Select-String -Path "passport_designer\__init__.py" -Pattern '^__version__ = "([0-9]+\.[0-9]+\.[0-9]+)"'
if (-not $match) { throw "__version__ not found in passport_designer\__init__.py / versie niet gevonden" }
$version = $match.Matches[0].Groups[1].Value
$exeName = "iAsset Passport Designer v$version"

python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name "$exeName" `
    --icon "passport_designer\assets\iasset-passport-designer.ico" `
    --add-data "passport_designer\data;passport_designer\data" `
    --add-data "passport_designer\assets;passport_designer\assets" `
    main.py
Write-Host "Klaar / Done: $PSScriptRoot\dist\$exeName.exe"
