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
import secrets
from typing import Optional

import paramiko

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.server import Server
from app.models.switch import Switch
from infrastructure.ssh_worker import SSHWorker, TerminalManager, BUF_SIZE
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


def parse_private_key(privatekey: str, passphrase: str) -> Optional[paramiko.PKey]:
    from io import StringIO
    try:
        key_io = StringIO(privatekey.strip())
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


# ─── POST /connect ──────────────────────────────────────────────────────────

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
    if not (is_valid_hostname(host) or is_valid_ip(host)):
        raise HTTPException(status_code=400, detail="Invalid hostname")
    if not is_valid_port(port):
        raise HTTPException(status_code=400, detail="Invalid port")
    if not username:
        raise HTTPException(status_code=400, detail="Username required")

    if not check_online(host, port=port, timeout=5):
        raise HTTPException(status_code=503, detail=f"Cannot reach {host}:{port}")

    pkey = None
    if privatekey:
        pkey = parse_private_key(privatekey, passphrase)

    if not encoding:
        encoding = 'utf-8'
    elif not is_valid_encoding(encoding):
        encoding = 'utf-8'

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

    asyncio.create_task(recycle_worker(worker, delay=30.0))

    return {"id": worker.id, "encoding": worker.encoding}


def _sync_ssh_connect(host, port, username, password, pkey, term, encoding) -> SSHWorker:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            host, port=port, username=username, password=password, pkey=pkey,
            timeout=10, look_for_keys=False, allow_agent=False,
        )
    except socket.error as e:
        raise ValueError(f"Unable to connect to {host}:{port}: {e}")
    except paramiko.BadAuthenticationType:
        raise ValueError("Bad authentication type")
    except paramiko.AuthenticationException:
        raise ValueError("Authentication failed")
    except paramiko.BadHostKeyException:
        raise ValueError("Bad host key")

    detected_encoding = encoding
    if not encoding or encoding == 'utf-8':
        try:
            detected_encoding = get_default_encoding(ssh)
        except Exception:
            detected_encoding = 'utf-8'

    chan = ssh.invoke_shell(term=term)
    chan.setblocking(0)

    worker = SSHWorker(
        ssh_client=ssh,
        channel=chan,
        dst_addr=(host, port),
        encoding=detected_encoding,
    )
    worker.id = secrets.token_urlsafe(32)
    TerminalManager.add_worker(host, worker)

    logger.info(f"[TerminalManager] Created worker {worker.id} for {host}:{port}")
    return worker


async def recycle_worker(worker: SSHWorker, delay: float = 30.0):
    await asyncio.sleep(delay)
    if not worker.handler:
        logger.warning(f"[TerminalManager] Recycling worker {worker.id} (no handler)")
        await worker.close(reason="worker recycled")
        TerminalManager.remove_worker(worker.dst_addr[0], worker.id)


# ─── WebSocket /ws ─────────────────────────────────────────────────────────

@router.websocket("/ws")
async def terminal_websocket(websocket: WebSocket):
    import sys
    print(f"[WS] incoming query={dict(websocket.query_params)}", flush=True, file=sys.stderr)

    await websocket.accept()
    print("[WS] accepted", flush=True, file=sys.stderr)

    worker_id = websocket.query_params.get("id")
    if not worker_id:
        print("[WS] no worker_id, closing", flush=True, file=sys.stderr)
        await websocket.close(code=4000, reason="Missing worker id")
        return

    print(f"[WS] looking up worker_id={worker_id}, registry={list(TerminalManager.clients.keys())}", flush=True, file=sys.stderr)
    worker: Optional[SSHWorker] = None
    for ip_workers in TerminalManager.clients.values():
        w = ip_workers.get(worker_id)
        if w and not w.handler:
            worker = w
            break

    if not worker:
        print(f"[WS] worker not found, closing", flush=True, file=sys.stderr)
        await websocket.close(code=4001, reason="Worker not found or already connected")
        return

    print(f"[WS] found worker {worker.id}, setting handler", flush=True, file=sys.stderr)
    worker.set_handler(websocket)

    reader_task = None
    try:
        reader_task = asyncio.create_task(_ssh_reader(worker))
        print(f"[WS] reader task started for {worker.id}", flush=True, file=sys.stderr)

        while True:
            msg = await websocket.receive_text()
            print(f"[WS] received msg len={len(msg)} data={repr(msg[:80])}", flush=True, file=sys.stderr)
            await handle_ws_message(worker, msg)

    except WebSocketDisconnect:
        print(f"[WS] WebSocketDisconnect for {worker.id}", flush=True, file=sys.stderr)
        logger.info(f"[TerminalManager] WebSocket disconnected for worker {worker.id}")
    except Exception as e:
        import traceback
        print(f"[WS] Exception for {worker.id}: {type(e).__name__}: {e}", flush=True, file=sys.stderr)
        logger.error(f"[TerminalManager] WebSocket error for worker {worker.id}: {e}\n{traceback.format_exc()}")
    finally:
        print(f"[WS] finally: cancelling reader, closing worker {worker.id}", flush=True, file=sys.stderr)
        if reader_task:
            reader_task.cancel()
        await worker.close(reason="WebSocket closed")
        for ip, workers in list(TerminalManager.clients.items()):
            if worker_id in workers:
                TerminalManager.remove_worker(ip, worker_id)
                break
        print(f"[WS] cleanup done for {worker.id}", flush=True, file=sys.stderr)


async def handle_ws_message(worker: SSHWorker, message: str):
    import sys
    try:
        msg = json.loads(message)
    except json.JSONDecodeError:
        return

    if not isinstance(msg, dict):
        return

    resize = msg.get("resize")
    if resize and isinstance(resize, list) and len(resize) == 2:
        try:
            worker.chan.resize_pty(int(resize[0]), int(resize[1]))
            print(f"[handle_ws] pty resized to {resize}", flush=True, file=sys.stderr)
        except Exception as e:
            print(f"[handle_ws] resize error: {e}", flush=True, file=sys.stderr)

    data = msg.get("data")
    if data and isinstance(data, str):
        try:
            data_bytes = data.encode(worker.encoding)
            sent = worker.chan.send(data_bytes)
            print(f"[handle_ws] sent {sent}/{len(data_bytes)} bytes", flush=True, file=sys.stderr)
        except OSError as e:
            print(f"[handle_ws] OSError on send: {e}", flush=True, file=sys.stderr)
            await worker.close(reason="channel write error")


async def _ssh_reader(worker: SSHWorker):
    import sys
    loop = asyncio.get_running_loop()
    print(f"[_ssh_reader] started for worker {worker.id}", flush=True, file=sys.stderr)

    def _sync_recv():
        """Sync recv - runs in thread pool, never blocks the asyncio loop."""
        try:
            return worker.chan.recv(BUF_SIZE)
        except Exception:
            return None  # None means error/closed

    try:
        while not worker.closed:
            # Use run_in_executor so chan.recv() (which can block) runs in a thread
            # This avoids the event loop blocking if recv() hangs
            data = await loop.run_in_executor(None, _sync_recv)

            if worker.closed:
                break

            if data is None:  # exception in thread
                print(f"[_ssh_reader] recv returned None (error)", flush=True, file=sys.stderr)
                await worker.close(reason="chan recv error")
                break

            if not data:  # empty = EOF
                print(f"[_ssh_reader] recv returned empty (eof)", flush=True, file=sys.stderr)
                await worker.close(reason="chan eof")
                break

            # Forward to WebSocket
            if worker.handler and not worker.closed:
                try:
                    await worker.handler.send_bytes(data)
                except Exception as e:
                    print(f"[_ssh_reader] send_bytes error: {e}", flush=True, file=sys.stderr)
                    await worker.close(reason="websocket closed")
                    break

    except Exception as e:
        import traceback
        print(f"[_ssh_reader] unexpected error: {type(e).__name__}: {e}", flush=True, file=sys.stderr)
        logger.error(f"[_ssh_reader] worker {worker.id}: {e}\n{traceback.format_exc()}")
    finally:
        print(f"[_ssh_reader] finished for worker {worker.id}", flush=True, file=sys.stderr)
