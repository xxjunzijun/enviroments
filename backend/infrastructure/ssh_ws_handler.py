"""
Infrastructure Layer - WebSocket SSH Handler
Bridges browser (xterm.js) <-> WebSocket <-> paramiko invoke_shell()
Reference: https://github.com/huashengdun/webssh
"""

import asyncio
import json
import threading
import uuid
import queue
import warnings
from typing import Optional

import paramiko
from paramiko import AutoAddPolicy

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

    def _read_from_channel(self, data_cb):
        """Background thread: read from SSH channel, send to WebSocket via queue."""
        import time
        while self.running:
            if self.channel is None:
                break
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(65535)
                    if data:
                        self.ws_queue.put(("data", data.decode("utf-8", errors="replace")))
                else:
                    time.sleep(0.01)
            except Exception:
                break

        # Channel closed
        try:
            self.ws_queue.put(("close", b""))
        except Exception:
            pass

    def _connect(self):
        """Background thread: establish SSH connection."""
        import time

        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())

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
        self.channel.settimeout(0.05)
        self.channel.setblocking(False)

        # Drain initial banner output
        time.sleep(0.5)
        try:
            while self.channel.recv_ready():
                self.channel.recv(65535)
        except Exception:
            pass

        # Check if password change is prompted (some Linux SSH servers do this)
        try:
            self.channel.send("\r\n")
            time.sleep(0.3)
            if self.channel.recv_ready():
                banner = self.channel.recv(65535).decode("utf-8", errors="replace")
                if "Change now" in banner or "[Y/N]" in banner:
                    self.channel.send("N\r\n")
                    time.sleep(0.3)
                    try:
                        while self.channel.recv_ready():
                            self.channel.recv(65535)
                    except Exception:
                        pass
        except Exception:
            pass

        self.running = True

        # Start reader thread
        reader = threading.Thread(target=self._read_from_channel, daemon=True)
        reader.start()

        # Notify connected
        self.ws_queue.put(("connected", ""))

    def start(self):
        t = threading.Thread(target=self._connect, daemon=True)
        t.start()

    def write(self, data: str):
        """Write data to SSH channel (from WebSocket -> SSH)."""
        if self.channel and self.running:
            try:
                self.channel.send(data)
            except Exception:
                pass

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
