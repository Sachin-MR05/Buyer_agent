$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "buyer-agent-core"
$frontendDir = Join-Path $root "buyer-agent-frontend"
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python virtual environment not found at $pythonExe"
    exit 1
}

if (-not (Test-Path $backendDir)) {
    Write-Error "Backend folder not found at $backendDir"
    exit 1
}

if (-not (Test-Path $frontendDir)) {
    Write-Error "Frontend folder not found at $frontendDir"
    exit 1
}

Write-Host "Starting buyer-agent backend..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-WorkingDirectory", $backendDir,
    "-Command",
    "& '$pythonExe' -m uvicorn main:app --reload --port 8010"
) | Out-Null

Write-Host "Starting buyer-agent frontend..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-WorkingDirectory", $frontendDir,
    "-Command",
    "npm run dev"
) | Out-Null

Write-Host "Both services started."
Write-Host "Backend: http://localhost:8010"
Write-Host "Frontend: http://localhost:5173"
