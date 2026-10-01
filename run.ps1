# RajPSP Student Profile Scraper PowerShell Launcher
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  RajPSP Student Profile Scraper" -ForegroundColor White
Write-Host "  Signal Blue (#0057FF) / Porcelain (#F8F7F4)" -ForegroundColor Blue
Write-Host "========================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    & $VenvPython (Join-Path $ScriptDir "app.py")
} else {
    python (Join-Path $ScriptDir "app.py")
}
