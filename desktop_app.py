import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import webview


APP_DIR = Path(__file__).resolve().parent
APP_FILE = APP_DIR / "app.py"
HOST = "127.0.0.1"
PORT = 8501
URL = f"http://{HOST}:{PORT}"


def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def wait_for_streamlit(url, timeout_seconds=30):
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)

    return False


def start_streamlit():
    if is_port_open(HOST, PORT):
        return None

    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP_FILE),
            "--server.address",
            HOST,
            "--server.port",
            str(PORT),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(APP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main():
    streamlit_process = start_streamlit()

    if not wait_for_streamlit(URL):
        if streamlit_process:
            streamlit_process.terminate()

        raise RuntimeError("DecisionVault AI could not start the local app server.")

    window = webview.create_window(
        "DecisionVault AI",
        URL,
        width=1320,
        height=900,
        min_size=(1040, 720),
    )

    try:
        webview.start()
    finally:
        if streamlit_process:
            streamlit_process.terminate()
            streamlit_process.wait(timeout=5)


if __name__ == "__main__":
    main()
