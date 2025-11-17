@echo off
setlocal EnableDelayedExpansion

set ROOT=%~dp0
set BACKEND_HOST=0.0.0.0
set BACKEND_PORT=8000
set FRONTEND_PORT=5173

if not "%1"=="" set BACKEND_HOST=%1
if not "%2"=="" set BACKEND_PORT=%2
if not "%3"=="" set FRONTEND_PORT=%3

if not exist "%ROOT%backend" (
    echo Backend folder not found: %ROOT%backend
    exit /b 1
)
if not exist "%ROOT%frontend" (
    echo Frontend folder not found: %ROOT%frontend
    exit /b 1
)

start "Capital Backend" cmd /k "cd /d %ROOT%backend && python -m uvicorn app.main:app --reload --host %BACKEND_HOST% --port %BACKEND_PORT%"
start "Capital Frontend" cmd /k "cd /d %ROOT%frontend && npm run dev -- --host --port %FRONTEND_PORT%"

echo Backend and frontend have been launched in separate windows.
echo Use CTRL+C in those windows or close them to stop the services.
pause
