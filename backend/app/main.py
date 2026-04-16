import os
import sys
import asyncio
import warnings
import queue
import json
import concurrent.futures

# Suppress paramiko cryptography deprecation warnings
warnings.filterwarnings("ignore", message="TripleDES has been moved")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="cryptography")

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse
from app.core.database import init_db, SessionLocal
from app.core.auth import decode_token
from app.api.v1.routers import servers, files, switches
from app.api.v1.routers import logs as logs_router
from app.api.v1.routers.logs import switch_logs_router
from app.api.v1.routers import auth
from app.models.server import Server
from app.models.switch import Switch
from infrastructure.ssh_ws_handler import create_session, close_session


def get_frontend_dist():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "frontend", "dist")
    else:
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "frontend", "dist"
        )


FRONTEND_DIST = get_frontend_dist()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Start background scheduler after database init
    from app.core.scheduler import create_scheduler
    scheduler = create_scheduler(app)
    scheduler.start()
    print("[Enviroments] Background scheduler started")
    yield
    scheduler.shutdown()
    print("[Enviroments] Background scheduler stopped")


app = FastAPI(title="Enviroments", version="1.0.0", lifespan=lifespan)

app.include_router(servers.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(logs_router.router, prefix="/api/v1")
app.include_router(switches.router, prefix="/api/v1")
app.include_router(switch_logs_router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")

@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

@app.get("/assets/{filename}")
def assets(filename: str):
    return FileResponse(os.path.join(FRONTEND_DIST, "assets", filename))


@app.websocket("/ws/ssh")
async def websocket_ssh(
    websocket: WebSocket,
    token: str = Query(...),
    target_type: str = Query(...),  # "server" or "switch"
    target_id: int = Query(...),
):
    """
    WebSocket SSH terminal endpoint.
    Connects to a managed server or switch via SSH interactive shell.
    """
    import sys
    print(f"[WS SSH] incoming connection: target_type={target_type}, target_id={target_id}", flush=True)

    # 1. Validate JWT
    await websocket.accept()
    user_id = decode_token(token)
    print(f"[WS SSH] token decoded: user_id={user_id}", flush=True)
    if user_id is None:
        print("[WS SSH] auth failed: invalid token", flush=True)
        await websocket.send_json({"type": "error", "data": "Unauthorized"})
        await websocket.close()
        return

    # 2. Get DB session and fetch target
    db = SessionLocal()
    try:
        if target_type == "server":
            target = db.query(Server).filter(Server.id == target_id).first()
            print(f"[WS SSH] server query result: {target}", flush=True)
            if not target:
                print(f"[WS SSH] server {target_id} not found", flush=True)
                await websocket.send_json({"type": "error", "data": "Server not found"})
                await websocket.close()
                return
            host = target.ip
            ssh_port = target.port or 22
            username = target.ssh_username
            password = target.ssh_password
        elif target_type == "switch":
            target = db.query(Switch).filter(Switch.id == target_id).first()
            print(f"[WS SSH] switch query result: {target}", flush=True)
            if not target:
                print(f"[WS SSH] switch {target_id} not found", flush=True)
                await websocket.send_json({"type": "error", "data": "Switch not found"})
                await websocket.close()
                return
            host = target.ip
            ssh_port = target.port or 22
            username = target.username
            password = target.password
        else:
            print(f"[WS SSH] invalid target_type: {target_type}", flush=True)
            await websocket.send_json({"type": "error", "data": "Invalid target_type"})
            await websocket.close()
            return
        print(f"[WS SSH] connecting SSH: host={host}, port={ssh_port}, username={username}", flush=True)
    finally:
        db.close()

    # 3. Create SSH session
    session_id, session = create_session(
        host=host,
        port=ssh_port,
        username=username,
        password=password,
    )
    print(f"[WS SSH] session created: {session_id}", flush=True)

    try:
        # 4. Drain SSH -> WebSocket events in a task
        # Non-blocking send strategy: use run_in_executor with a thread pool.
        # The pump loop (async) never blocks; it schedules sync send tasks
        # into a thread pool. The thread doing the actual send will block on
        # TCP write (if buffer is full) but that doesn't affect the async loop.
        # The async loop stays free to run receive_text() -> user input ->
        # SSH -> more queue data -> deadlock broken.
        pending_futures: set = set()
        _loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        def _sync_send(payload: dict):
            """Synchronous send running in thread pool — does NOT block the async loop."""
            try:
                print(f"[WS SSH] _sync_send[{payload.get('type')}]: encoding + sending", flush=True)
                text = json.dumps(payload, separators=(",", ":"))
                # Submit async send to event loop from this thread
                # asyncio.run_coroutine_threadsafe schedules coroutine on the loop
                # running in the main thread; the future is returned but we
                # don't wait on it here (fire-and-forget).
                asyncio.run_coroutine_threadsafe(websocket.send_text(text), _loop)
                print(f"[WS SSH] _sync_send[{payload.get('type')}]: submitted OK", flush=True)
            except Exception as e:
                print(f"[WS SSH] _sync_send ERROR [{payload.get('type')}]: {type(e).__name__}: {e}", flush=True)

        async def pump_ssh_to_ws():
            """Pump messages from SSH session queue -> WebSocket."""
            ws_queue = session.get_queue()
            print(f"[WS SSH] pump started for session {session_id}", flush=True)

            def schedule_send(payload: dict):
                """Fire-and-forget: submit sync send to thread pool."""
                fut = _executor.submit(_sync_send, payload)
                fut.add_done_callback(lambda f: pending_futures.discard(f) or _check_future(f))
                pending_futures.add(fut)
                print(f"[WS SSH] schedule_send: queued {payload.get('type')}, pending={len(pending_futures)}", flush=True)

            def _check_future(f):
                try:
                    f.result()
                except Exception as e:
                    print(f"[WS SSH] future failed: {e}", flush=True)

            # Wait for connected signal first
            try:
                msg_type, data = ws_queue.get(timeout=15)
                print(f"[WS SSH] pump got msg: type={msg_type}, data={repr(data[:50]) if data else ''}", flush=True)
                if msg_type == "error":
                    schedule_send({"type": "error", "data": data})
                    print(f"[WS SSH] pump: got error, exiting", flush=True)
                    return
                elif msg_type == "connected":
                    schedule_send({"type": "connected"})
                elif msg_type == "close":
                    print(f"[WS SSH] pump: got close before connected, exiting", flush=True)
                    return
            except queue.Empty:
                print(f"[WS SSH] pump: timeout waiting for connected, exiting", flush=True)
                return

            # Normal message pump loop — non-blocking sends only
            while True:
                try:
                    msg_type, data = ws_queue.get(timeout=0.05)
                    print(f"[WS SSH] pump got msg: type={msg_type}, data={repr(data[:50]) if data else ''}", flush=True)
                    if msg_type == "data":
                        schedule_send({"type": "data", "data": data})
                    elif msg_type == "connected":
                        schedule_send({"type": "connected"})
                    elif msg_type == "error":
                        print(f"[WS SSH] SSH error: {data}", flush=True)
                        schedule_send({"type": "error", "data": data})
                    elif msg_type == "close":
                        break
                except queue.Empty:
                    if not session.running:
                        print(f"[WS SSH] pump: session.running=False, exiting", flush=True)
                        break
                    continue
                except Exception as e:
                    print(f"[WS SSH] pump exception: {e}", flush=True)
                    break
            print(f"[WS SSH] pump exiting for session {session_id}", flush=True)

        pump_task = asyncio.create_task(pump_ssh_to_ws())

        # 5. Receive from WebSocket -> SSH
        # IMPORTANT: session.write() and session.resize() MUST run in a thread
        # pool. Calling them directly would block the event loop because
        # channel.send() is a synchronous blocking call. If the event loop
        # blocks here, the pump task (which also needs the event loop to run
        # websocket.send_text via asyncio.run_coroutine_threadsafe) cannot
        # proceed -> deadlock.  ThreadPoolExecutor ensures the blocking
        # paramiko calls don't stall the asyncio event loop.
        _write_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        async def async_write(data: str):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_write_executor, session.write, data)

        async def async_resize(w: int, h: int):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_write_executor, session.resize, w, h)

        while True:
            try:
                raw = await websocket.receive_text()
                print(f"[WS SSH] received: {repr(raw[:100])}", flush=True)
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    # Plain text: treat as terminal input
                    await async_write(raw)
                    continue

                msg_type = msg.get("type")
                if msg_type == "input":
                    await async_write(msg.get("data", ""))
                elif msg_type == "resize":
                    w = msg.get("width", 200)
                    h = msg.get("height", 80)
                    await async_resize(w, h)
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                print(f"[WS SSH] WebSocket disconnected", flush=True)
                break
            except Exception as e:
                print(f"[WS SSH] receive exception: {e}", flush=True)
                break

    finally:
        print(f"[WS SSH] cleanup: cancelling pump, closing session {session_id}", flush=True)
        pump_task.cancel()
        close_session(session_id)
        print(f"[WS SSH] cleanup done", flush=True)


if getattr(sys, 'frozen', False):
    import uvicorn
    print(f"[Enviroments] FRONTEND_DIST = {FRONTEND_DIST}")
    print(f"[Enviroments] Exists: {os.path.exists(FRONTEND_DIST)}")

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())