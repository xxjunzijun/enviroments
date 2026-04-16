"""
Infrastructure Layer - SSH WebSocket Worker
Based on huashengdun/webssh, adapted for FastAPI + Starlette
Uses asyncio event loop to monitor SSH channel fd (no threads).
"""

import asyncio
import logging
from typing import Optional, Dict

import paramiko

BUF_SIZE = 32 * 1024

logger = logging.getLogger(__name__)


class SSHWorker:
    """
    Manages a single SSH shell session + WebSocket connection.
    
    Uses asyncio event loop to monitor the SSH channel's socket fd.
    No threads — pure async I/O like webssh's Worker.
    """

    def __init__(
        self,
        ssh_client: paramiko.SSHClient,
        channel,
        dst_addr: tuple,
        encoding: str = "utf-8",
    ):
        self.ssh = ssh_client
        self.chan = channel
        self.dst_addr = dst_addr  # (ip, port) of SSH server
        self.fd = channel.fileno()
        self.id = None  # assigned by TerminalManager
        self.encoding = encoding
        
        # Queue of data to send to SSH server
        self.data_to_dst: list = []
        
        # WebSocket handler (set after connection)
        self.handler = None
        self.mode = 1  # 1=READ, 2=WRITE (IOLoop-style constants)
        self.closed = False
        self._write_ready = True  # simulate IOLoop WRITE tracking

    def set_handler(self, handler):
        """Set the WebSocket handler and switch to non-blocking."""
        self.handler = handler
        # Set SSH channel non-blocking so recv doesn't block the loop
        self.chan.setblocking(0)

    # ── IOLoop-style fd handler ──────────────────────────────────────────────

    async def handle_read(self):
        """Called when SSH channel has data to read (READ event)."""
        try:
            data = self.chan.recv(BUF_SIZE)
        except OSError as e:
            logger.error(f"[Worker {self.id}] recv error: {e}")
            await self.close(reason="chan error on reading")
            return

        if not data:
            await self.close(reason="chan closed")
            return

        logger.debug(f"[Worker {self.id}] recv {len(data)} bytes from {self.dst_addr}")
        if self.handler:
            try:
                await self.handler.send_bytes(data)
            except Exception:
                await self.close(reason="websocket closed")

    async def handle_write(self):
        """Called when SSH channel is ready for writing (WRITE event)."""
        if not self.data_to_dst:
            return

        data = "".join(self.data_to_dst)
        logger.debug(f"[Worker {self.id}] send {len(data)} bytes to {self.dst_addr}")

        try:
            sent = self.chan.send(data)
        except OSError as e:
            logger.error(f"[Worker {self.id}] send error: {e}")
            await self.close(reason="chan error on writing")
            return

        self.data_to_dst = []
        remaining = data[sent:]
        if remaining:
            self.data_to_dst.append(remaining)
            # Channel buffer full — will be called again
        else:
            # All sent — switch back to READ mode
            self.mode = 1  # READ

    async def handle_close(self):
        """Close the worker gracefully."""
        if self.closed:
            return
        self.closed = True
        logger.info(f"[Worker {self.id}] Closing worker, reason: cleanup")
        try:
            if self.handler:
                await self.handler.close()
        except Exception:
            pass
        try:
            self.chan.close()
        except Exception:
            pass
        try:
            self.ssh.close()
        except Exception:
            pass
        logger.info(f"[Worker {self.id}] Connection to {self.dst_addr} closed")

    async def close(self, reason: str = None):
        """Public close method."""
        if self.closed:
            return
        self.closed = True
        logger.info(f"[Worker {self.id}] Closing worker, reason: {reason}")
        try:
            if self.handler:
                await self.handler.close()
        except Exception:
            pass
        try:
            self.chan.close()
        except Exception:
            pass
        try:
            self.ssh.close()
        except Exception:
            pass
        logger.info(f"[Worker {self.id}] Connection to {self.dst_addr} closed")


class TerminalManager:
    """
    Global registry for active SSH sessions (per IP, per worker ID).
    Mimics webssh's `clients` dict but with async support.
    """
    clients: Dict[str, Dict[str, SSHWorker]] = {}  # {ip: {worker_id: worker}}

    @classmethod
    def add_worker(cls, ip: str, worker: SSHWorker):
        if ip not in cls.clients:
            cls.clients[ip] = {}
        cls.clients[ip][worker.id] = worker

    @classmethod
    def remove_worker(cls, ip: str, worker_id: str):
        workers = cls.clients.get(ip, {})
        workers.pop(worker_id, None)
        if not workers:
            cls.clients.pop(ip, None)

    @classmethod
    def get_worker(cls, ip: str, worker_id: str) -> Optional[SSHWorker]:
        workers = cls.clients.get(ip)
        if not workers:
            return None
        return workers.get(worker_id)

    @classmethod
    def clear_ip(cls, ip: str):
        """Remove all workers for an IP (e.g., on disconnect)."""
        cls.clients.pop(ip, None)


def _generate_worker_id() -> str:
    """Generate a secure random worker ID."""
    import secrets
    return secrets.token_urlsafe(32)


async def ssh_connect_and_start_shell(
    ip: str,
    port: int,
    username: str,
    password: Optional[str],
    pkey=None,
    term: str = "xterm",
    encoding: str = "utf-8",
    dst_ip: str = None,
) -> SSHWorker:
    """
    Connect to SSH server, open an interactive shell, and return a Worker.
    This is called in a thread pool since paramiko is blocking.
    """
    import socket

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            ip,
            port=port,
            username=username,
            password=password,
            pkey=pkey,
            timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )
    except socket.error as e:
        raise ValueError(f"Unable to connect to {ip}:{port}: {e}")
    except paramiko.BadAuthenticationType:
        raise ValueError("Bad authentication type")
    except paramiko.AuthenticationException:
        raise ValueError("Authentication failed")
    except paramiko.BadHostKeyException:
        raise ValueError("Bad host key")

    # Invoke interactive shell
    chan = ssh.invoke_shell(term=term)
    chan.setblocking(0)  # non-blocking

    worker = SSHWorker(
        ssh_client=ssh,
        channel=chan,
        dst_addr=(ip, port),
        encoding=encoding,
    )
    worker.id = _generate_worker_id()

    # Register
    src_ip = dst_ip or ip
    TerminalManager.add_worker(src_ip, worker)

    logger.info(f"[TerminalManager] Created worker {worker.id} for {ip}:{port}")
    return worker


async def recycle_worker(worker: SSHWorker, delay: float = 30.0):
    """Schedule worker cleanup after delay if no WebSocket connected."""
    await asyncio.sleep(delay)
    if not worker.handler:
        logger.warning(f"[TerminalManager] Recycling worker {worker.id} (no handler)")
        await worker.close(reason="worker recycled")
        TerminalManager.remove_worker(worker.dst_addr[0], worker.id)
