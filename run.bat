@echo off
title RajPSP Student Profile Scraper
cd /d "%~dp0"

echo ========================================================
echo   RajPSP Student Profile Scraper
echo   Primary Colors: Signal Blue (#0057FF) / Porcelain (#F8F7F4)
echo ========================================================

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Starting Desktop Application...
"%PYTHON_EXE%" app.py

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
