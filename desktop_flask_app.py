import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import webview


APP_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 5050
URL = f"http://{HOST}:{PORT}"


def wait_for_app(url, timeout_seconds=30):
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.35)

    return False


def main():
    process = subprocess.Popen(
        [sys.executable, "flask_app.py"],
        cwd=str(APP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    if not wait_for_app(URL):
        process.terminate()
        raise RuntimeError("DecisionVault AI could not start.")

    try:
        webview.create_window(
            "DecisionVault AI",
            URL,
            width=1360,
            height=920,
            min_size=(1060, 760),
        )
        webview.start()
    finally:
        process.terminate()
        process.wait(timeout=5)


if __name__ == "__main__":
    main()
