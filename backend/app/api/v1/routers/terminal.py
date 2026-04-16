"""
SSH Web Terminal API - WebSocket based (webssh pattern)
POST /api/v1/terminal/connect  -> 创建 session，返回 worker_id
WebSocket /api/v1/terminal/ws  -> 交互数据
"""

import asyncio
import json
import logging
import re
import socket
import struct
import io
from typing import Optional

import paramiko

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.server import Server
from app.models.switch import Switch
from infrastructure.ssh_worker import (
    SSHWorker, TerminalManager, ssh_connect_and_start_shell,
    recycle_worker, BUF_SIZE
)
from infrastructure.ssh_client import check_online

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/terminal", tags=["terminal"])


# ─── Helpers ────────────────────────────────────────────────────────────────

def is_valid_encoding(encoding: str) -> bool:
    try:
        "test".encode(encoding)
        return True
    except (LookupError, ValueError):
        return False


def get_default_encoding(ssh) -> str:
    """Detect SSH server's default encoding by running locale."""
    commands = [
        '$SHELL -ilc "locale charmap"',
        '$SHELL -ic "locale charmap"'
    ]
    for cmd in commands:
        try:
            _, stdout, _ = ssh.exec_command(cmd, get_pty=True, timeout=1)
        except Exception:
            continue
        try:
            data = stdout.read()
        except socket.timeout:
            continue
        if data:
            try:
                encoding = data.strip().decode('ascii')
                if is_valid_encoding(encoding):
                    return encoding
            except Exception:
                pass
    return 'utf-8'


def parse_unicode(s: str) -> Optional[str]:
    """Parse a unicode string from client message."""
    try:
        return str(s)
    except Exception:
        return None


# ─── POST /connect - Create SSH session ────────────────────────────────────

@router.post("/connect")
async def terminal_connect(
    host: str,
    port: int = 22,
    username: str = None,
    password: str = None,
    privatekey: str = None,
    passphrase: str = None,
    totp: str = None,
    term: str = "xterm",
    encoding: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Connect to SSH server and create a terminal session.
    Returns worker_id for WebSocket connection.
    """
    # Validate host
    if not (is_valid_hostname(host) or is_valid_ip(host)):
        raise HTTPException(status_code=400, detail="Invalid hostname")

    if not is_valid_port(port):
        raise HTTPException(status_code=400, detail="Invalid port")

    if not username:
        raise HTTPException(status_code=400, detail="Username required")

    # Check online
    if not check_online(host, port=port, timeout=5):
        raise HTTPException(status_code=503, detail=f"Cannot reach {host}:{port}")

    # Parse private key if provided
    pkey = None
    if privatekey:
        pkey = parse_private_key(privatekey, passphrase)

    # Get encoding
    if not encoding:
        encoding = 'utf-8'
    elif not is_valid_encoding(encoding):
        encoding = 'utf-8'

    # Connect in thread pool (paramiko is blocking)
    loop = asyncio.get_event_loop()
    try:
        worker: SSHWorker = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                _sync_ssh_connect,
                host, port, username, password, pkey, term, encoding
            ),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="SSH connection timeout")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"SSH connect error: {e}")
        raise HTTPException(status_code=500, detail="SSH connection failed")

    # Get client IP for worker registry
    client_ip = host  # will be updated with actual client IP in ws

    # Schedule recycling if no WebSocket connects within 30s
    asyncio.create_task(recycle_worker(worker, delay=30.0))

    return {
        "id": worker.id,
        "encoding": worker.encoding,
    }


def _sync_ssh_connect(host, port, username, password, pkey, term, encoding) -> SSHWorker:
    """Synchronous SSH connect (runs in thread pool)."""
    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            host,
            port=port,
            username=username,
            password=password,
            pkey=pkey,
            timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )
    except socket.error as e:
        raise ValueError(f"Unable to connect to {host}:{port}: {e}")
    except paramiko.BadAuthenticationType:
        raise ValueError("Bad authentication type")
    except paramiko.AuthenticationException:
        raise ValueError("Authentication failed")
    except paramiko.BadHostKeyException:
        raise ValueError("Bad host key")

    # Detect encoding
    detected_encoding = encoding
    if not encoding or encoding == 'utf-8':
        try:
            detected_encoding = get_default_encoding(ssh)
        except Exception:
            detected_encoding = 'utf-8'

    # Invoke shell
    chan = ssh.invoke_shell(term=term)
    chan.setblocking(0)

    # Generate worker ID
    import secrets
    worker_id = secrets.token_urlsafe(32)

    from infrastructure.ssh_worker import SSHWorker
    worker = SSHWorker(
        ssh_client=ssh,
        channel=chan,
        dst_addr=(host, port),
        encoding=detected_encoding,
    )
    worker.id = worker_id

    # Register
    TerminalManager.add_worker(host, worker)

    logger.info(f"[TerminalManager] Created worker {worker.id} for {host}:{port}")
    return worker


def parse_private_key(privatekey: str, passphrase: str) -> Optional[paramiko.PKey]:
    """Parse a private key string into a paramiko PKey."""
    import paramiko
    from io import StringIO

    try:
        key_io = StringIO(privatekey.strip())
        # Detect key type from header
        line = privatekey.strip().split('\n')[0]
        if 'RSA' in line:
            name = 'RSA'
        elif 'DSA' in line:
            name = 'DSS'
        elif 'EC' in line:
            name = 'ECDSA'
        elif 'OPENSSH' in line:
            name = 'Ed25519'
        else:
            name = None

        pkey = None
        if name:
            try:
                pkey_cls = getattr(paramiko, name + 'Key')
                pkey = pkey_cls.from_private_key(key_io, password=passphrase)
            except paramiko.SSHException:
                pass

        # Fallback: try all types
        if not pkey and name == 'Ed25519':
            for n in ['RSA', 'ECDSA', 'DSS']:
                try:
                    pkey_cls = getattr(paramiko, n + 'Key')
                    key_io.seek(0)
                    pkey = pkey_cls.from_private_key(key_io, password=passphrase)
                    break
                except Exception:
                    continue

        return pkey
    except Exception as e:
        logger.warning(f"Failed to parse private key: {e}")
        return None


def is_valid_ip(ip: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def is_valid_hostname(hostname: str) -> bool:
    if len(hostname) > 253:
        return False
    allowed = re.compile(r'(?!-)[a-z0-9-]{1,63}(?<!-)$', re.IGNORECASE)
    labels = hostname.split('.')
    return all(allowed.match(label) for label in labels)


def is_valid_port(port: int) -> bool:
    return 0 < port < 65536


# ─── WebSocket /ws - Terminal session ─────────────────────────────────────

@router.websocket("/ws")
async def terminal_websocket(websocket: WebSocket):
    """
    WebSocket terminal session.
    Connect with query param: ?id=<worker_id>
    Messages: JSON {\"data\": \"...\"} or {\"resize\": [width, height]}
    """
    await websocket.accept()

    # Get worker_id from query
    worker_id = websocket.query_params.get("id")
    if not worker_id:
        await websocket.close(code=4000, reason="Missing worker id")
        return

    # Find worker - search across all IPs
    worker: Optional[SSHWorker] = None
    for ip_workers in TerminalManager.clients.values():
        w = ip_workers.get(worker_id)
        if w and not w.handler:
            worker = w
            break

    if not worker:
        import sys
        print(f'[DIAG] Worker {worker_id} not found. Registry={list(TerminalManager.clients.keys())}', flush=True, file=sys.stderr)
        await websocket.close(code=4001, reason='Worker not found or already connected')
        return

    # Mark as connected
    worker.set_handler(websocket)

    # Get client IP for registry
    # Note: we don't update TerminalManager with client IP since we already registered

    logger.info(f"[TerminalManager] WebSocket connected for worker {worker.id}")

    try:
        # Start the SSH → WebSocket reader task
        reader_task = asyncio.create_task(_ssh_reader(worker))

        # Handle incoming WebSocket messages
        while True:
            msg = await websocket.receive_text()
            await handle_ws_message(worker, msg)

    except WebSocketDisconnect:
        logger.info(f"[TerminalManager] WebSocket disconnected for worker {worker.id}")
    except Exception as e:
        logger.error(f"[TerminalManager] WebSocket error for worker {worker.id}: {e}")
    finally:
        reader_task.cancel()
        await worker.close(reason="WebSocket closed")
        # Remove from registry
        for ip, workers in TerminalManager.clients.items():
            if worker_id in workers:
                TerminalManager.remove_worker(ip, worker_id)
                break


async def handle_ws_message(worker: SSHWorker, message: str):
    """Handle a JSON message from WebSocket client."""
    try:
        msg = json.loads(message)
    except json.JSONDecodeError:
        return

    if not isinstance(msg, dict):
        return

    # Handle resize
    resize = msg.get("resize")
    if resize and isinstance(resize, list) and len(resize) == 2:
        try:
            worker.chan.resize_pty(int(resize[0]), int(resize[1]))
        except Exception:
            pass

    # Handle data
    data = msg.get("data")
    if data and isinstance(data, str):
        # Convert to bytes using worker's encoding
        try:
            if isinstance(data, str):
                data_bytes = data.encode(worker.encoding)
            else:
                data_bytes = data

            # Write to SSH channel
            try:
                sent = worker.chan.send(data_bytes)
                if sent == 0:
                    # Buffer full - append to pending
                    worker.data_to_dst.append(data)
                elif sent < len(data_bytes):
                    worker.data_to_dst.append(data_bytes[sent:].decode(worker.encoding, errors='replace'))
            except OSError:
                await worker.close(reason="channel write error")
        except Exception as e:
            logger.error(f"[Worker {worker.id}] send error: {e}")


async def _ssh_reader(worker: SSHWorker):
    """
    Background task: read from SSH channel and forward to WebSocket.
    Uses polling since paramiko channel isn't natively awaitable.
    """
    while not worker.closed:
        try:
            # Poll with timeout
            await asyncio.sleep(0.01)  # 10ms polling

            if worker.closed:
                break

            try:
                data = worker.chan.recv(BUF_SIZE)
            except OSError:
                await worker.close(reason="chan closed")
                break

            if not data:
                await worker.close(reason="chan eof")
                break

            if worker.handler and not worker.closed:
                try:
                    await worker.handler.send_bytes(data)
                except Exception:
                    await worker.close(reason="websocket closed")
                    break

        except Exception as e:
            logger.error(f"[Worker {worker.id}] reader error: {e}")
            break
