import os
import sys
import warnings

# Suppress paramiko cryptography deprecation warnings
warnings.filterwarnings("ignore", message="TripleDES has been moved")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="cryptography")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.core.database import init_db
from app.api.v1.routers import servers, files, logs, switches


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
app.include_router(logs.router, prefix="/api/v1")
app.include_router(switches.router, prefix="/api/v1")

@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

@app.get("/assets/{filename}")
def assets(filename: str):
    return FileResponse(os.path.join(FRONTEND_DIST, "assets", filename))


if getattr(sys, 'frozen', False):
    import asyncio
    import uvicorn
    print(f"[Enviroments] FRONTEND_DIST = {FRONTEND_DIST}")
    print(f"[Enviroments] Exists: {os.path.exists(FRONTEND_DIST)}")

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())