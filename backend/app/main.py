import os
import sys
import asyncio
import warnings
import queue
import json

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
    # 1. Validate JWT
    await websocket.accept()
    user_id = decode_token(token)
    if user_id is None:
        await websocket.send_json({"type": "error", "data": "Unauthorized"})
        await websocket.close()
        return

    # 2. Get DB session and fetch target
    db = SessionLocal()
    try:
        if target_type == "server":
            target = db.query(Server).filter(Server.id == target_id).first()
            if not target:
                await websocket.send_json({"type": "error", "data": "Server not found"})
                await websocket.close()
                return
            host = target.ip
            port = target.port or 22
            username = target.username
            password = target.password
        elif target_type == "switch":
            target = db.query(Switch).filter(Switch.id == target_id).first()
            if not target:
                await websocket.send_json({"type": "error", "data": "Switch not found"})
                await websocket.close()
                return
            host = target.ip
            port = target.port or 22
            username = target.username
            password = target.password
        else:
            await websocket.send_json({"type": "error", "data": "Invalid target_type"})
            await websocket.close()
            return
    finally:
        db.close()

    # 3. Create SSH session
    session_id, session = create_session(
        host=host,
        port=port,
        username=username,
        password=password,
    )

    try:
        # 4. Drain SSH -> WebSocket events in a task
        async def pump_ssh_to_ws():
            """Pump messages from SSH session queue -> WebSocket."""
            ws_queue = session.get_queue()
            while True:
                try:
                    msg_type, data = ws_queue.get(timeout=0.05)
                    if msg_type == "data":
                        await websocket.send_json({"type": "data", "data": data})
                    elif msg_type == "connected":
                        await websocket.send_json({"type": "connected"})
                    elif msg_type == "error":
                        await websocket.send_json({"type": "error", "data": data})
                    elif msg_type == "close":
                        break
                except queue.Empty:
                    # Check if session is still running
                    if not hasattr(session, 'running') or not session.running:
                        break
                    continue
                except Exception:
                    break

        pump_task = asyncio.create_task(pump_ssh_to_ws())

        # 5. Receive from WebSocket -> SSH
        while True:
            try:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    # Plain text: treat as terminal input
                    session.write(raw)
                    continue

                msg_type = msg.get("type")
                if msg_type == "input":
                    session.write(msg.get("data", ""))
                elif msg_type == "resize":
                    w = msg.get("width", 200)
                    h = msg.get("height", 80)
                    session.resize(w, h)
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            except Exception:
                break

    finally:
        pump_task.cancel()
        close_session(session_id)


if getattr(sys, 'frozen', False):
    import uvicorn
    print(f"[Enviroments] FRONTEND_DIST = {FRONTEND_DIST}")
    print(f"[Enviroments] Exists: {os.path.exists(FRONTEND_DIST)}")

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())