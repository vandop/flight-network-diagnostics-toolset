"""Integration test ensuring the Python client and server communicate."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = REPO_ROOT / "server"
CLIENT_DIR = REPO_ROOT / "clients" / "python"


@pytest.mark.integration
@pytest.mark.timeout(120)
def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.25)
    raise TimeoutError(f"Server did not start listening on {host}:{port} within {timeout} seconds")


def test_python_client_server_round_trip(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    with (SERVER_DIR / "config.yaml").open("r", encoding="utf8") as f:
        server_config = yaml.safe_load(f)
    with (CLIENT_DIR / "config.yaml").open("r", encoding="utf8") as f:
        client_config = yaml.safe_load(f)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        _, port = sock.getsockname()

    server_log = tmp_path / "server.log"
    client_log = tmp_path / "client.log"

    server_config["server"]["port"] = int(port)
    server_config["server"]["log_file"] = str(server_log)
    host = "127.0.0.1"
    client_config["client"]["port"] = int(port)
    client_config["client"]["host"] = host
    client_config["client"]["log_file"] = str(client_log)
    client_config["client"]["repetitions"] = 2
    client_config["client"]["interval"]["initial_ms"] = 0

    server_config_path = tmp_path / "server_config.yaml"
    client_config_path = tmp_path / "client_config.yaml"
    with server_config_path.open("w", encoding="utf8") as f:
        yaml.safe_dump(server_config, f)
    with client_config_path.open("w", encoding="utf8") as f:
        yaml.safe_dump(client_config, f)

    server_cmd = [sys.executable, "-m", "server.flight_server", "--config", str(server_config_path)]
    client_cmd = [sys.executable, "-m", "clients.python.flight_client", "--config", str(client_config_path)]

    server_env = env.copy()
    client_env = env.copy()

    server_proc = subprocess.Popen(server_cmd, cwd=REPO_ROOT, env=server_env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
    client_proc: subprocess.CompletedProcess[str] | None = None
    try:
        _wait_for_port(host, int(port))

        client_proc = subprocess.run(client_cmd, cwd=REPO_ROOT, env=client_env, check=False,
                                     capture_output=True, text=True)
        if client_proc.returncode != 0:
            raise AssertionError(
                f"Client failed with code {client_proc.returncode}\nSTDOUT:\n{client_proc.stdout}\nSTDERR:\n{client_proc.stderr}"
            )

        # Allow server to process the last request.
        time.sleep(2)
    finally:
        server_proc.send_signal(signal.SIGINT)
        try:
            stdout, _ = server_proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            stdout, _ = server_proc.communicate()

    server_output = stdout if stdout else ""
    assert "Sending echo response" in server_output

    assert client_proc is not None
    client_stdout = client_proc.stdout
    assert "Received response" in client_stdout

    # Validate that the client saw a JSON response with metadata.
    last_response_line = next(
        line for line in reversed(client_stdout.splitlines()) if "Received response" in line
    )
    payload = json.loads(last_response_line.split("Received response: ", 1)[1])
    assert "metadata" in payload
    assert "delay_applied_seconds" in payload["metadata"]
