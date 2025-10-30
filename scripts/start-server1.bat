@echo off
REM start-server.bat - delegate to scripts\start_server.py (centralized starter)
SETLOCAL ENABLEDELAYEDEXPANSION
SET "ROOT=%~dp0.."
cd /d "%ROOT%"

REM Prefer system python to run the central starter (the script will create venv if needed)
where python >nul 2>nul
IF %ERRORLEVEL%==0 (
    python "%ROOT%\scripts\start_server.py"
    goto :EOF
)

where py >nul 2>nul
IF %ERRORLEVEL%==0 (
    py -3 "%ROOT%\scripts\start_server.py"
    goto :EOF
)

echo No 'python' or 'py' launcher found on PATH. Please install Python 3 and ensure 'python' or 'py' is available.
exit /b 1