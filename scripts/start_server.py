import sys
import subprocess
import time
from pathlib import Path
import webbrowser
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
if sys.platform.startswith("win"):
    VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PY = ROOT / ".venv" / "bin" / "python"

URL = "http://127.0.0.1:8000/"


def ensure_venv():
    if not VENV_PY.exists():
        print("Creating virtual environment...")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", str(ROOT / ".venv")])
        except subprocess.CalledProcessError as exc:
            print("Failed to create virtualenv using the current Python executable:", exc)
            # On Windows try the 'py -3' launcher as a fallback (common when multiple Pythons exist)
            if sys.platform.startswith("win"):
                try:
                    print("Attempting to create venv using 'py -3'...")
                    subprocess.check_call(["py", "-3", "-m", "venv", str(ROOT / ".venv")])
                    print("Virtual environment created using 'py -3'.")
                except FileNotFoundError:
                    print("'py' launcher not found on PATH. Please ensure Python 3 is installed and available as 'python' or 'py -3'.")
                    raise
                except subprocess.CalledProcessError as exc2:
                    print("Failed to create virtualenv using 'py -3':", exc2)
                    raise
            else:
                raise


def install_requirements():
    req = ROOT / "requirements.txt"
    if req.exists():
        print("Installing requirements...")
        try:
            subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip"])
            subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-r", str(req)])
        except subprocess.CalledProcessError as exc:
            print("pip install failed:", exc)
            print("Possible actions:")
            print(f" - Inspect the error above and try running: {str(VENV_PY)} -m pip install -r {str(req)}")
            print(" - Check network connectivity / proxy settings if downloads fail.")
            print(" - If SSL errors occur, try upgrading certifi in the venv: ")
            print(f"   {str(VENV_PY)} -m pip install --upgrade certifi")
            raise


def wait_for_server(url=URL, timeout=10.0, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0):
                return True
        except Exception:
            time.sleep(interval)
    return False


def open_browser():
    try:
        ready = wait_for_server()
        if not ready:
            print(f"Server did not respond within timeout; opening browser anyway: {URL}")
        webbrowser.open_new_tab(URL)
        print(f"Opened {URL} in default browser (new tab requested)")
    except Exception as e:
        print("Failed to open browser:", e)


def start_uvicorn():
    env_file = str(ROOT / ".env")
    cmd = [
        str(VENV_PY),
        "-m",
        "uvicorn",
        "dv_admin_automator.ui.web.server:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--env-file",
        env_file,
    ]
    print("Starting uvicorn:", " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=str(ROOT))
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()


def main():
    ensure_venv()
    install_requirements()
    proc = subprocess.Popen([
        str(VENV_PY),
        "-m",
        "uvicorn",
        "dv_admin_automator.ui.web.server:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--env-file",
        str(ROOT / ".env"),
    ], cwd=str(ROOT))
    try:
        if wait_for_server(timeout=8.0):
            open_browser()
        else:
            print("Server did not respond in time; opening browser anyway.")
            open_browser()
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
