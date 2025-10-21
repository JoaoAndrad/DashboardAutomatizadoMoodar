@echo off
REM start-server.bat - start the server using .venv and open browser (Windows cmd.exe)
SETLOCAL ENABLEDELAYEDEXPANSION
SET "ROOT=%~dp0"
cd /d "%ROOT%..\"

REM create venv if missing
IF NOT EXIST ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM upgrade pip and install requirements (if present)
".venv\Scripts\python.exe" -m pip install --upgrade pip
IF EXIST requirements.txt (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

REM Create temporary PowerShell watcher script that launches browser and uvicorn,
REM waits for uvicorn to exit and then kills the browser and removes the temp profile.
SET "PS1=%TEMP%\moodar_run_%RANDOM%.ps1"

REM Use PowerShell Set-Content with a here-string to avoid cmd parsing/parenthesis issues
REM Write the PowerShell watcher content line-by-line to avoid quoting issues.
REM Overwrite/create the file with the first line, then append the rest.
ECHO $root = (Get-Location).Path > "%PS1%"
ECHO $venv = Join-Path $root '.venv\Scripts\python.exe' >> "%PS1%"
ECHO $url = 'http://127.0.0.1:8000/' >> "%PS1%"
ECHO # Open the URL in the default (last-used) browser as a new tab. This will reuse an existing browser process if present.
ECHO Start-Process $url >> "%PS1%"
ECHO # Start uvicorn in a new window (PowerShell window) so user sees logs >> "%PS1%"
ECHO $uv_cmd = "& `"$venv`" -m uvicorn dv_admin_automator.ui.web.server:app --reload --host 127.0.0.1 --port 8000" >> "%PS1%"
ECHO $uv = Start-Process -FilePath 'powershell' -ArgumentList '-NoExit','-Command',$uv_cmd -PassThru >> "%PS1%"
ECHO Write-Output ("Started uvicorn (pid=" + $uv.Id + ") and opened URL in default browser") >> "%PS1%"
ECHO $uv.WaitForExit() >> "%PS1%"

REM Run the watcher PowerShell script (this will block until uvicorn exits)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"

REM cleanup watcher script
DEL /F /Q "%PS1%" 2>nul

pause