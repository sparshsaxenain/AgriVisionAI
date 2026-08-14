"""One-command local launcher for the AgriVision API and farmer interface."""
from __future__ import annotations

import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent


def wait_for_api(url: str, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(url, timeout=1).ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(.4)
    return False


def main() -> None:
    from scripts.seed_database import seed

    seed()
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT)
    frontend = None
    try:
        if not wait_for_api("http://127.0.0.1:8000/health"):
            raise RuntimeError("The API did not start. Review the message above.")
        frontend = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.address=127.0.0.1", "--server.port=8501", "--server.headless=true"], cwd=ROOT)
        print("\nAgriVision AI is ready: http://127.0.0.1:8501")
        print("API documentation: http://127.0.0.1:8000/docs")
        print("Press Ctrl+C to stop both services.\n")
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8501")
        while frontend.poll() is None and backend.poll() is None:
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (frontend, backend):
            if process and process.poll() is None:
                process.terminate()
        for process in (frontend, backend):
            if process:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()

