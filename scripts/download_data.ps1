# Download raw open data for Montreal Transit Intelligence (run locally on Windows).
# Upload the resulting files to Databricks: /FileStore/mti/raw/

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RawDir = Join-Path $Root "data\raw"
New-Item -ItemType Directory -Force -Path $RawDir | Out-Null

$StmUrl = "https://donneesouvertes.stm.info/fichiers/Incidents%20m%C3%A9tro.csv"
$StmOut = Join-Path $RawDir "stm_incidents_metro.csv"

Write-Host "Downloading STM metro incidents..."
curl.exe -sL $StmUrl -o $StmOut
$stmSize = (Get-Item $StmOut).Length
Write-Host "STM CSV: $StmOut ($stmSize bytes)"

Write-Host "Downloading weather (YUL daily) via Python..."
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Push-Location $Root
& $Python -m pip install -e . -q
& $Python scripts/download_weather.py
Pop-Location

Write-Host "Downloading Canadiens home game schedule (NHL API)..."
& $Python scripts/download_canadiens_schedule.py

Write-Host "Downloading Montreal 311 daily aggregates (optional, large download)..."
& $Python scripts/download_311.py

$RefExperience = Join-Path $Root "data\reference\stm_experience_yearly.csv"
$RawExperience = Join-Path $RawDir "stm_experience_yearly.csv"
if (Test-Path $RefExperience) {
    Copy-Item -Force $RefExperience $RawExperience
    Write-Host "Copied STM experience reference to $RawExperience"
}

Write-Host "Done. Upload data/raw/* to your Databricks volume (see docs/DATABRICKS_SETUP.md)."
