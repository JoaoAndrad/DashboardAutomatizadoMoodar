Start-server scripts

Files:

- start-server.ps1 - PowerShell script that creates/uses `.venv`, installs `requirements.txt` if needed, starts the uvicorn server and opens the dashboard in the default browser.
- start-server.bat - Equivalent for cmd.exe users (Windows).

Usage (PowerShell):
Open PowerShell in the repository root and run:

./scripts/start-server.ps1

Options:
-Host <host> (default 127.0.0.1)
-Port <port> (default 8000)
-OpenPath <path> (default /static/dashboard.html)
-Install Force pip install of requirements

Examples:
./scripts/start-server.ps1 -Port 8001
./scripts/start-server.ps1 -Install

Notes:

- The script assumes `python` is available on PATH. On Windows, use the same Python installation used to create the project's virtual environment.
- The script will create a `.venv` directory in the repository root if missing.
- Uvicorn is started with `--reload` for developer convenience. Remove it for production.
