"""
Infrastructure Layer - WebSocket SSH Handler
Bridges browser (xterm.js) <-> WebSocket <-> paramiko invoke_shell()
Reference: https://github.com/huashengdun/webssh
"""

import asyncio
import json
import threading
import time
import uuid
import queue
import warnings
from typing import Optional

import paramiko
from paramiko import AutoAddPolicy


class _AllowAnyHostKeyPolicy(paramiko.client.MissingHostKeyPolicy):
    """Accept any host key — for trusted private network servers only."""
    def missing_host_key(self, client, hostname, key):
        # Accept any key without verification
        pass

# Suppress paramiko deprecation warnings
warnings.filterwarnings("ignore", message="TripleDES has been moved")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="cryptography")


# Global session registry: session_id -> SSHChannelSession
_sessions: dict[str, "SSHChannelSession"] = {}
_sessions_lock = threading.Lock()


class SSHChannelSession:
    """
    Manages a single SSH interactive shell session.
    Runs paramiko in a background thread, communicates with WebSocket in the main thread.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str],
        key_file: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_file = key_file

        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.channel = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.ws_queue: queue.Queue = queue.Queue()
        self.running = False

    def _read_from_channel(self):
        """Background thread: read from SSH channel using blocking recv with timeout."""
        import time
        print(f"[SSH reader] thread started, channel={self.channel}", flush=True)
        recv_count = 0
        while self.running:
            if self.channel is None:
                print(f"[SSH reader] channel is None, exiting", flush=True)
                break
            try:
                data = self.channel.recv(65535)
                if data:
                    recv_count += 1
                    print(f"[SSH reader] recv #{recv_count}, len={len(data)}", flush=True)
                    self.ws_queue.put(("data", data.decode("utf-8", errors="replace")))
            except Exception as e:
                etype = type(e).__name__
                # setblocking(0) causes BlockingIOError when no data available.
                # socket.timeout (settimeout) also raises here. Both mean "no data
                # right now, keep waiting" — don't break the loop.
                if etype in ("BlockingIOError", "timeout") or "timeout" in etype.lower():
                    # No data — sleep briefly to avoid busy-polling
                    time.sleep(0.01)
                else:
                    print(f"[SSH reader] exception: {etype}: {e}", flush=True)
                    break
                continue

        print(f"[SSH reader] loop exited (recv_count={recv_count})", flush=True)
        self.running = False
        try:
            self.ws_queue.put(("close", ""))
        except Exception:
            pass

    def _connect(self):
        """Background thread: establish SSH connection."""
        import time

        self.ssh_client = paramiko.SSHClient()
        # Use empty host keys to skip known_hosts verification (private network only)
        self.ssh_client.get_host_keys().clear()
        self.ssh_client.set_missing_host_key_policy(_AllowAnyHostKeyPolicy())

        try:
            self.ssh_client.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                key_filename=self.key_file,
                timeout=10,
                look_for_keys=False,
                allow_agent=False,
                # Disable password change prompt interaction (answer N)
                auth_timeout=10,
            )
        except Exception as e:
            self.ws_queue.put(("error", str(e)))
            return

        # Handle password change prompt for Linux servers
        self.channel = self.ssh_client.invoke_shell(width=200, height=80)
        self.channel.setblocking(0)  # non-blocking, rely on select() in reader loop
        print(f"[SSH reader] invoke_shell done, channel={self.channel}", flush=True)

        # Drain initial banner output and send to WebSocket via queue
        time.sleep(0.5)
        all_data = b''
        drain_count = 0
        while True:
            try:
                d = self.channel.recv(65535)
                if d:
                    all_data += d
                    drain_count += 1
                    print(f"[SSH reader] drain recv #{drain_count} {len(d)} bytes", flush=True)
                else:
                    break
            except Exception as e:
                etype = type(e).__name__
                if etype in ("BlockingIOError", "timeout") or "timeout" in etype.lower():
                    break
                else:
                    print(f"[SSH reader] drain exception: {e}", flush=True)
                    break
        print(f"[SSH reader] total drained: {len(all_data)} bytes", flush=True)
        if all_data:
            self.ws_queue.put(("data", all_data.decode("utf-8", errors="replace")))

        # Send newline to trigger fresh shell prompt
        try:
            self.channel.send("\r\n")
        except Exception as e:
            print(f"[SSH reader] send newline failed: {e}", flush=True)

        # Start reader thread, then notify connected
        self.running = True
        reader = threading.Thread(target=self._read_from_channel, daemon=True)
        reader.start()
        time.sleep(0.2)  # Let reader stabilize before any channel I/O

        print(f"[SSH reader] _connect done, connected", flush=True)
        self.ws_queue.put(("connected", ""))

    def start(self):
        t = threading.Thread(target=self._connect, daemon=True)
        t.start()

    def write(self, data: str) -> bool:
        """Write data to SSH channel (from WebSocket -> SSH). Returns True on success."""
        print(f"[SSH write] called with: {repr(data)}", flush=True)
        if not self.channel:
            print(f"[SSH write] skipped: channel is None", flush=True)
            return False
        if not self.running:
            print(f"[SSH write] skipped: not running", flush=True)
            return False
        try:
            sent = self.channel.send(data)
            print(f"[SSH write] sent {sent} bytes", flush=True)
            if sent == 0:
                print(f"[SSH write] WARNING: sent=0, channel buffer may be full", flush=True)
                return False
            return True
        except Exception as e:
            print(f"[SSH write] error: {type(e).__name__}: {e}", flush=True)
            raise  # Re-raise so caller (run_in_executor) sees the error

    def resize(self, width: int, height: int):
        """Resize terminal window."""
        if self.channel and self.running:
            try:
                self.channel.resize(width=width, height=height)
            except Exception:
                pass

    def close(self):
        """Close SSH session."""
        self.running = False
        try:
            if self.channel:
                self.channel.close()
        except Exception:
            pass
        try:
            if self.ssh_client:
                self.ssh_client.close()
        except Exception:
            pass

    def get_queue(self) -> queue.Queue:
        return self.ws_queue


def create_session(
    host: str,
    port: int,
    username: str,
    password: Optional[str],
    key_file: Optional[str] = None,
) -> tuple[str, SSHChannelSession]:
    """Create a new SSH session and return (session_id, session)."""
    session_id = str(uuid.uuid4())[:8]
    session = SSHChannelSession(host, port, username, password, key_file)
    with _sessions_lock:
        _sessions[session_id] = session
    session.start()
    return session_id, session


def get_session(session_id: str) -> Optional[SSHChannelSession]:
    with _sessions_lock:
        return _sessions.get(session_id)


def close_session(session_id: str):
    """Close and remove a session."""
    with _sessions_lock:
        session = _sessions.pop(session_id, None)
    if session:
        session.close()
