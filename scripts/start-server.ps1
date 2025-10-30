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

Write-Host "Delegating to scripts/start_server.py (centralized starter)."

# Try to run the central starter using the active python interpreter. The script
# will create the venv if necessary and start uvicorn (with --env-file).
try {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python (Join-Path $root 'scripts\start_server.py')
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 (Join-Path $root 'scripts\start_server.py')
    }
    else {
        Write-Error "No 'python' or 'py' launcher found on PATH. Please install Python 3 and ensure 'python' or 'py' is available."
        exit 1
    }
}
catch {
    Write-Error "Failed to run scripts/start_server.py: $_"
    exit 1
}