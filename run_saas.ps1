# RajPSP SaaS Platform & REST API Server Launcher
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  RajPSP SaaS Platform & Developer REST API Server" -ForegroundColor White
Write-Host "  Running on:  http://localhost:8085" -ForegroundColor Green
Write-Host "  Admin Panel: http://localhost:8085/admin/" -ForegroundColor Yellow
Write-Host "  Widget Demo: http://localhost:8085/widget/demo/" -ForegroundColor Yellow
Write-Host "  API Docs:    http://localhost:8085/widget/docs/" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    & $VenvPython (Join-Path $ScriptDir "manage.py") runserver 0.0.0.0:8085
} else {
    python (Join-Path $ScriptDir "manage.py") runserver 0.0.0.0:8085
}
