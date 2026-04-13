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
    init_db()
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
