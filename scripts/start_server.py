import sys
import subprocess
import time
from pathlib import Path
import webbrowser
import urllib.request
import urllib.error
import os
import signal
import re

ROOT = Path(__file__).resolve().parent.parent
# venv lives inside the project root (ROOT/.venv)
if sys.platform.startswith("win"):
    VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PY = ROOT / ".venv" / "bin" / "python"

URL = "http://127.0.0.1:8000/"


def ensure_venv():
    # Create venv inside the project root if missing
    if not VENV_PY.exists():
        print("Creating virtual environment in project (ROOT/.venv) ...")
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
        print("Installing requirements (if needed)...")
        try:
            if requirements_satisfied(req):
                print("Requirements already satisfied in venv; skipping installation.")
                return
        except Exception:
            # fall back to installing if the check fails
            pass

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


def parse_requirements_file(req_path: Path):
    reqs = []
    if not req_path.exists():
        return reqs
    with req_path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "#" in line:
                line = line.split("#", 1)[0].strip()
            m = re.match(r"^([A-Za-z0-9_.+-]+)\s*([<>=!~]+)\s*([0-9a-zA-Z.+-]+)$", line)
            if m:
                name, op, ver = m.group(1), m.group(2), m.group(3)
                reqs.append((name, op, ver))
            else:
                bare = line.split()[0]
                reqs.append((bare, "", ""))
    return reqs


def get_installed_packages():
    try:
        out = subprocess.check_output([str(VENV_PY), "-m", "pip", "freeze"], universal_newlines=True)
    except Exception:
        return {}
    inst = {}
    for line in out.splitlines():
        if "==" in line:
            parts = line.split("==", 1)
            inst[parts[0].lower()] = parts[1]
    return inst


def requirements_satisfied(req_path: Path) -> bool:
    reqs = parse_requirements_file(req_path)
    if not reqs:
        return True
    installed = get_installed_packages()
    for name, op, ver in reqs:
        key = name.lower()
        if not op:
            return False
        if op == "==":
            if key not in installed:
                return False
            if installed[key] != ver:
                return False
        else:
            return False
    return True


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
    """Open the UI URL using Google Chrome only. If Chrome is running, open a new tab
    in the existing Chrome process. If Chrome is not found, print a message and
    fall back to webbrowser.open_new_tab as a last resort.
    """
    try:
        ready = wait_for_server()
        if not ready:
            print(f"Server did not respond within timeout; opening browser anyway: {URL}")

        # Prefer Google Chrome specifically
        chrome_cmd = find_chrome_command()
        if chrome_cmd:
            try:
                # If chrome_cmd contains space (like 'py -3' equivalent), split
                parts = chrome_cmd.split()
                # Launch Chrome to open URL (this will open a new tab in existing instance)
                subprocess.Popen(parts + [URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Opened {URL} in Google Chrome")
                return
            except Exception as e:
                print("Failed to launch Chrome directly:", e)

        # Fallback to default browser if Chrome not available
        webbrowser.open_new_tab(URL)
        print(f"Opened {URL} in default browser (new tab requested)")
    except Exception as e:
        print("Failed to open browser:", e)


def find_chrome_command():
    """Return a best-effort command name for Google Chrome on this platform, or
    None if not found. Examples returned: 'chrome' (Windows), 'google-chrome'
    (Linux), 'open -a "Google Chrome"' (macOS handled separately by returning
    '/usr/bin/open').
    """
    if sys.platform.startswith("win"):
        # On Windows, 'chrome' should be on PATH when Chrome is installed in default location
        # Use 'where' to detect presence
        try:
            subprocess.check_call(["where", "chrome"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "chrome"
        except Exception:
            return None
    elif sys.platform.startswith("darwin"):
        # macOS: use 'open -a "Google Chrome" <url>'
        # We'll return '/usr/bin/open' and caller will append ['-a', 'Google Chrome', URL]
        try:
            # check if Chrome app exists
            chrome_path = "/Applications/Google Chrome.app"
            if os.path.exists(chrome_path):
                return "/usr/bin/open -a 'Google Chrome'"
        except Exception:
            return None
        return None
    else:
        # Linux: common binary names
        for name in ("google-chrome", "chrome", "chromium", "chromium-browser"):
            try:
                subprocess.check_call(["which", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return name
            except Exception:
                continue
        return None


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
    # Before starting, find and terminate any processes listening on port 8000
    try:
        pids = find_pids_listening_on_port(8000)
        if pids:
            print(f"Found processes listening on port 8000: {pids}. Terminating...")
            terminate_pids(pids, force=True)
            time.sleep(0.5)
    except Exception:
        pass

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
