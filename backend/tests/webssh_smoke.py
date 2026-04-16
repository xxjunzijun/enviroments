"""
Smoke test for the Web SSH flow.

It exercises the same two-step protocol used by the Vue WebTerminal:

1. Register or log in to obtain a Bearer token.
2. POST /api/v1/terminal/connect to create an SSH worker.
3. Connect to /api/v1/terminal/ws?id=<worker_id>, send a command, and read output.

Run against a locally started backend, for example:

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Then in another shell:

    python tests/webssh_smoke.py --ssh-host 127.0.0.1 --ssh-user user --ssh-password pass

You can also set WEBSSH_HOST, WEBSSH_USER, WEBSSH_PASSWORD, WEBSSH_PORT,
WEBSSH_BASE_URL, WEBSSH_LOGIN_USER, and WEBSSH_LOGIN_PASSWORD.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
import websockets


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_LOGIN_USER = "webssh_smoke"
DEFAULT_LOGIN_PASSWORD = "password123"


@dataclass
class SmokeConfig:
    base_url: str
    login_user: str
    login_password: str
    ssh_host: str
    ssh_port: int
    ssh_user: str
    ssh_password: str
    command: str
    timeout: float


def parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Smoke test the Enviroments Web SSH API.")
    parser.add_argument("--base-url", default=os.getenv("WEBSSH_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--login-user", default=os.getenv("WEBSSH_LOGIN_USER", DEFAULT_LOGIN_USER))
    parser.add_argument("--login-password", default=os.getenv("WEBSSH_LOGIN_PASSWORD", DEFAULT_LOGIN_PASSWORD))
    parser.add_argument("--ssh-host", default=os.getenv("WEBSSH_HOST"))
    parser.add_argument("--ssh-port", type=int, default=int(os.getenv("WEBSSH_PORT", "22")))
    parser.add_argument("--ssh-user", default=os.getenv("WEBSSH_USER"))
    parser.add_argument("--ssh-password", default=os.getenv("WEBSSH_PASSWORD"))
    parser.add_argument("--command", default=os.getenv("WEBSSH_COMMAND", "echo WEBSSH_SMOKE_OK"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("WEBSSH_TIMEOUT", "20")))
    args = parser.parse_args()

    missing = [
        name
        for name, value in {
            "--ssh-host or WEBSSH_HOST": args.ssh_host,
            "--ssh-user or WEBSSH_USER": args.ssh_user,
            "--ssh-password or WEBSSH_PASSWORD": args.ssh_password,
        }.items()
        if not value
    ]
    if missing:
        parser.error("missing required SSH settings: " + ", ".join(missing))

    return SmokeConfig(
        base_url=args.base_url.rstrip("/"),
        login_user=args.login_user,
        login_password=args.login_password,
        ssh_host=args.ssh_host,
        ssh_port=args.ssh_port,
        ssh_user=args.ssh_user,
        ssh_password=args.ssh_password,
        command=args.command,
        timeout=args.timeout,
    )


def ws_url(base_url: str, worker_id: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc
    return f"{scheme}://{netloc}/api/v1/terminal/ws?id={worker_id}"


async def register_or_login(client: httpx.AsyncClient, config: SmokeConfig) -> str:
    payload = {"username": config.login_user, "password": config.login_password}

    register_response = await client.post("/api/v1/auth/register", json=payload)
    if register_response.status_code == 201:
        data = register_response.json()
        print(f"registered test user: {data['username']}")
        return data["access_token"]

    if register_response.status_code not in (400, 409):
        raise RuntimeError(
            f"register failed: HTTP {register_response.status_code} {register_response.text}"
        )

    login_response = await client.post("/api/v1/auth/login", json=payload)
    if login_response.status_code != 200:
        raise RuntimeError(f"login failed: HTTP {login_response.status_code} {login_response.text}")

    data = login_response.json()
    print(f"logged in as existing test user: {data['username']}")
    return data["access_token"]


async def create_worker(client: httpx.AsyncClient, token: str, config: SmokeConfig) -> dict[str, Any]:
    params = {
        "host": config.ssh_host,
        "port": config.ssh_port,
        "username": config.ssh_user,
        "password": config.ssh_password,
        "term": "xterm",
    }
    response = await client.post(
        f"/api/v1/terminal/connect?{urlencode(params)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code != 200:
        raise RuntimeError(f"terminal/connect failed: HTTP {response.status_code} {response.text}")

    data = response.json()
    if not data.get("id"):
        raise RuntimeError(f"terminal/connect did not return a worker id: {data!r}")

    print(f"created SSH worker: {data['id']}")
    return data


async def read_until_marker(websocket, marker: str, timeout: float) -> str:
    output_parts: list[str] = []
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        message = await asyncio.wait_for(websocket.recv(), timeout=remaining)

        if isinstance(message, bytes):
            text = message.decode("utf-8", errors="replace")
        else:
            try:
                payload = json.loads(message)
                text = str(payload.get("data", message))
            except json.JSONDecodeError:
                text = message

        output_parts.append(text)
        output = "".join(output_parts)
        if marker in output:
            return output

    raise TimeoutError(f"did not see marker {marker!r} within {timeout} seconds")


async def run_smoke(config: SmokeConfig) -> None:
    async with httpx.AsyncClient(base_url=config.base_url, timeout=config.timeout) as client:
        token = await register_or_login(client, config)
        worker = await create_worker(client, token, config)

    marker = f"WEBSSH_SMOKE_{int(time.time())}"
    command = config.command
    if "WEBSSH_SMOKE_OK" in command:
        command = command.replace("WEBSSH_SMOKE_OK", marker)
    else:
        command = f"{command}; echo {marker}"

    url = ws_url(config.base_url, worker["id"])
    print(f"connecting websocket: {url}")

    async with websockets.connect(url, open_timeout=config.timeout) as websocket:
        await websocket.send(json.dumps({"resize": [120, 40]}))
        await websocket.send(json.dumps({"data": command + "\n"}))
        output = await read_until_marker(websocket, marker, config.timeout)

    print("websocket command output contained marker")
    print("--- captured output ---")
    print(output[-2000:])


def main() -> int:
    config = parse_args()
    try:
        asyncio.run(run_smoke(config))
    except Exception as exc:
        print(f"WEBSSH SMOKE FAILED: {exc}", file=sys.stderr)
        return 1

    print("WEBSSH SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
