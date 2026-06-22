# Upload raw CSVs to Databricks Unity Catalog volume via CLI.
# Free Edition: /FileStore is DISABLED — use Volumes instead.
# Prerequisite: create volume first (run 00b_bootstrap_check in Databricks).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RawDir = Join-Path $Root "data\raw"

$Stm = Join-Path $RawDir "stm_incidents_metro.csv"
$Weather = Join-Path $RawDir "weather_yul_daily.csv"

foreach ($file in @($Stm, $Weather)) {
    if (-not (Test-Path $file)) {
        Write-Error "Missing $file — run .\scripts\download_data.ps1 first."
    }
}

$databricks = Get-Command databricks -ErrorAction SilentlyContinue
if (-not $databricks) {
    Write-Error "Databricks CLI not found. Upload via UI: Catalog → main → default → mti → raw"
}

# Default Free Edition path (adjust catalog if yours uses 'workspace')
$Dest = "dbfs:/Volumes/main/default/mti/raw"
Write-Host "Uploading to $Dest ..."
Write-Host "If this fails, create volume 'mti' in Databricks first (see docs/DATABRICKS_SETUP.md)"

databricks fs cp --overwrite $Stm "$Dest/stm_incidents_metro.csv"
databricks fs cp --overwrite $Weather "$Dest/weather_yul_daily.csv"

Write-Host "Done. Verify in Databricks notebook:"
Write-Host "  dbutils.fs.ls('/Volumes/main/default/mti/raw')"
