<#
Start-server.ps1
Windows PowerShell script to create a virtualenv, install dependencies and start the uvicorn server,
then open the dashboard page in the default browser.

Usage:
  .\start-server.ps1 [-Host "127.0.0.1"] [-Port 8000] [-OpenPath "/static/dashboard.html"] [-Install]

Options:
  -Host      Host to bind (default: 127.0.0.1)
  -Port      Port to bind (default: 8000)
  -OpenPath  Path to open in browser after server start (default: /static/dashboard.html)
  -Install   If present, force pip install of requirements (useful to ensure deps are installed)

This script assumes Git Bash/PowerShell environment on Windows and that Python 3.8+ is available
as the `python` command. It will create a .venv directory in the repository root if missing.
#>

param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [string]$OpenPath = "/static/dashboard.html",
    [switch]$Install
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# Ensure .venv exists
$venvPath = Join-Path $root ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (!(Test-Path $pythonExe)) {
    Write-Host "Creating virtual environment at $venvPath..."
    python -m venv .venv
} else {
    Write-Host "Using existing virtualenv: $venvPath"
}

# Upgrade pip and install requirements if requested or if requirements changed
$reqFile = Join-Path $root "requirements.txt"
if (Test-Path $reqFile) {
    if ($Install -or -not (Get-Command $pythonExe -ErrorAction SilentlyContinue)) {
        & $pythonExe -m pip install --upgrade pip
        & $pythonExe -m pip install -r $reqFile
    } else {
        # Try a quick check: if requirements was modified after venv created, offer to install
        $venvMTime = (Get-Item $venvPath).LastWriteTime
        $reqMTime = (Get-Item $reqFile).LastWriteTime
        if ($reqMTime -gt $venvMTime) {
            Write-Host "requirements.txt is newer than .venv; installing requirements..."
            & $pythonExe -m pip install --upgrade pip
            & $pythonExe -m pip install -r $reqFile
        } else {
            Write-Host "requirements appear up-to-date. Use -Install to force reinstall."
        }
    }
} else {
    Write-Host "No requirements.txt found at $reqFile. Skipping install step." -ForegroundColor Yellow
}

# Start uvicorn in a new background process
$serverModule = "dv_admin_automator.ui.web.server:app"
$uvicornArgs = "-m uvicorn $serverModule --reload --host $Host --port $Port --log-level info"

# Build the command that runs using the venv python
$startCmd = "`"$pythonExe`" -m uvicorn $serverModule --reload --host $Host --port $Port --log-level info"

Write-Host "Starting server: $startCmd"
# Start-Process so it doesn't block the script
Start-Process -FilePath $pythonExe -ArgumentList "-m","uvicorn",$serverModule,"--reload","--host",$Host,"--port",$Port,"--log-level","info" -WindowStyle Normal

# Wait a short time for the server to start
Start-Sleep -Seconds 1

$baseUrl = "http://$Host`:$Port"
$fullUrl = $baseUrl.TrimEnd('/') + $OpenPath

Write-Host "Opening $fullUrl in default browser..."
Start-Process $fullUrl

Write-Host "Server start command issued. Uvicorn runs in a separate process. Use task manager to stop it if needed."