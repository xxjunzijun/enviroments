import os
import sys
import warnings
import traceback

# Suppress paramiko cryptography deprecation warnings
warnings.filterwarnings("ignore", message="TripleDES has been moved")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="cryptography")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.core.database import init_db
from app.api.v1.routers import servers, files


def get_frontend_dist():
    """Get frontend dist path: works in both dev and frozen modes."""
    if getattr(sys, 'frozen', False):
        # In PyInstaller exe: files bundled under _MEIPASS/frontend/dist
        return os.path.join(sys._MEIPASS, "frontend", "dist")
    else:
        # Dev: backend/app/main.py → project root → frontend/dist
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "frontend", "dist"
        )


FRONTEND_DIST = get_frontend_dist()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        print(f"[STARTUP ERROR] Database init failed: {e}")
        traceback.print_exc()
    yield


app = FastAPI(title="Enviroments", version="1.0.0", lifespan=lifespan)

app.include_router(servers.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")

@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

@app.get("/assets/{filename}")
def assets(filename: str):
    return FileResponse(os.path.join(FRONTEND_DIST, "assets", filename))


# ── PyInstaller entry point ────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    import asyncio
    import uvicorn

    print(f"[Enviroments] Starting server...")
    print(f"[Enviroments] FRONTEND_DIST = {FRONTEND_DIST}")
    print(f"[Enviroments] Exists: {os.path.exists(FRONTEND_DIST)}")
    if not os.path.exists(FRONTEND_DIST):
        print(f"[Enviroments] ERROR: frontend dist not found at {FRONTEND_DIST}")
        print(f"[Enviroments] Contents of _MEIPASS ({sys._MEIPASS}):")
        for root_dir, dirs, files in os.walk(sys._MEIPASS):
            for d in dirs:
                print(f"  DIR: {os.path.relpath(os.path.join(root_dir, d), sys._MEIPASS)}")
            break

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
