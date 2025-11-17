param(
    [string]$BackendHost = "0.0.0.0",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

if (-not (Test-Path $backendDir)) {
    Write-Error "Backend folder not found: $backendDir"
    exit 1
}
if (-not (Test-Path $frontendDir)) {
    Write-Error "Frontend folder not found: $frontendDir"
    exit 1
}

$backendCmd = "Set-Location `"$backendDir`"; python -m uvicorn app.main:app --reload --host $BackendHost --port $BackendPort"
$frontendCmd = "Set-Location `"$frontendDir`"; npm run dev -- --host --port $FrontendPort"

Write-Host "Starting backend: $backendCmd" -ForegroundColor Cyan
$backendProc = Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $backendCmd -PassThru

Write-Host "Starting frontend: $frontendCmd" -ForegroundColor Cyan
$frontendProc = Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $frontendCmd -PassThru

Write-Host "Backend PID: $($backendProc.Id)" -ForegroundColor Green
Write-Host "Frontend PID: $($frontendProc.Id)" -ForegroundColor Green
Write-Host "Press ENTER to stop both services..." -ForegroundColor Yellow
[void][System.Console]::ReadLine()

Write-Host "Stopping frontend..." -ForegroundColor Yellow
if (!$frontendProc.HasExited) { Stop-Process -Id $frontendProc.Id }

Write-Host "Stopping backend..." -ForegroundColor Yellow
if (!$backendProc.HasExited) { Stop-Process -Id $backendProc.Id }
