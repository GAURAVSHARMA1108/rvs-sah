@echo off
title RajPSP SaaS Platform & REST API Server
cd /d "%~dp0"

echo ========================================================
echo   RajPSP SaaS Platform & Developer REST API Server
echo   Running at: http://localhost:8085
echo   Admin Panel: http://localhost:8085/admin/
echo   Widget Demo: http://localhost:8085/widget/demo/
echo   API Docs:    http://localhost:8085/widget/docs/
echo ========================================================

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" manage.py runserver 0.0.0.0:8085
pause
