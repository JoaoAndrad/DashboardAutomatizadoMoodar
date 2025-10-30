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
import sys
import subprocess

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


def find_pids_listening_on_port(port=8000):
    """Return a set of PIDs listening on the given TCP port on localhost.
    Uses platform tools: on Windows parses netstat -ano; on Unix tries lsof/ss/netstat.
    """
    pids = set()
    port_str = str(port)
    if sys.platform.startswith("win"):
        try:
            out = subprocess.check_output(["netstat", "-ano"], universal_newlines=True, stderr=subprocess.DEVNULL)
        except Exception:
            return pids
        for line in out.splitlines():
            if f":{port_str} " in line or f":{port_str}\t" in line or f":{port_str}\r" in line:
                parts = re.split(r"\s+", line.strip())
                if len(parts) >= 5:
                    pid = parts[-1]
                    state = parts[3] if len(parts) >= 4 else ""
                    # Look for LISTENING or any TCP row
                    try:
                        pids.add(int(pid))
                    except Exception:
                        continue
        return pids
    else:
        # Try lsof first
        try:
            out = subprocess.check_output(["lsof", "-nP", f"-iTCP:{port_str}", "-sTCP:LISTEN"], universal_newlines=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines()[1:]:
                parts = re.split(r"\s+", line.strip())
                if len(parts) >= 2:
                    try:
                        pids.add(int(parts[1]))
                    except Exception:
                        continue
            return pids
        except Exception:
            pass

        # Try ss
        try:
            out = subprocess.check_output(["ss", "-ltnp"], universal_newlines=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if f":{port_str} " in line or f":{port_str}\n" in line or f":{port_str}:" in line:
                    # look for pid=NUM or users:("prog",pid,
                    m = re.search(r"pid=(\d+)", line)
                    if m:
                        try:
                            pids.add(int(m.group(1)))
                        except Exception:
                            pass
            if pids:
                return pids
        except Exception:
            pass

        # Last resort: netstat parsing on Unix
        try:
            out = subprocess.check_output(["netstat", "-ltnp"], universal_newlines=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if f":{port_str} " in line:
                    parts = re.split(r"\s+", line.strip())
                    if len(parts) >= 7:
                        pidprog = parts[6]
                        if "/" in pidprog:
                            pid = pidprog.split("/")[0]
                            try:
                                pids.add(int(pid))
                            except Exception:
                                pass
            return pids
        except Exception:
            return pids


def terminate_pids(pids, force=False):
    """Attempt to terminate the provided PIDs. On Unix try SIGTERM then SIGKILL if needed.
    On Windows use taskkill /PID <pid> /F when force True or /PID <pid> otherwise.
    """
    if not pids:
        return
    for pid in list(pids):
        try:
            if sys.platform.startswith("win"):
                cmd = ["taskkill", "/PID", str(pid)]
                if force:
                    cmd.append("/F")
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    continue
        except Exception as e:
            # Best effort; continue attempting to kill other PIDs
            print(f"Failed to terminate PID {pid}: {e}")



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
