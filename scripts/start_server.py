#!/usr/bin/env python3
"""Cross-platform initializer used by platform-specific starters.

Responsibilities:
- ensure a .venv exists
- install requirements.txt into the venv (if present)
- open the default browser to the app URL (new tab)
- start uvicorn using the venv python and wait until it exits

This script intentionally avoids platform-specific terminal/window handling; the
wrappers (`.bat` and `.sh`) should open new terminals if a separate window is
desired.
"""
import sys
import subprocess
from pathlib import Path
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe" if sys.platform.startswith("win") else ROOT / ".venv" / "bin" / "python"
URL = "http://127.0.0.1:8000/"


def ensure_venv():
    if not VENV_PY.exists():
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(ROOT / ".venv")])


def install_requirements():
    req = ROOT / "requirements.txt"
    if req.exists():
        print("Installing requirements...")
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-r", str(req)])


def open_browser():
    try:
        webbrowser.open_new_tab(URL)
        print(f"Opened {URL} in default browser (new tab requested)")
    except Exception as e:
        print("Failed to open browser:", e)


def start_uvicorn():
    cmd = [str(VENV_PY), "-m", "uvicorn", "dv_admin_automator.ui.web.server:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]
    print("Starting uvicorn:", " ".join(cmd))
    proc = subprocess.Popen(cmd)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()


def main():
    ensure_venv()
    install_requirements()
    open_browser()
    start_uvicorn()


if __name__ == "__main__":
    main()
