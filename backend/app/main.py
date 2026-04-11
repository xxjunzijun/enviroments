import os
import sys

# Determine base path
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    # backend/app/main.py → project root (3 levels up)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.core.database import init_db
from app.api.v1.routers import servers

app = FastAPI(title="Enviroments", version="1.0.0")

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(servers.router, prefix="/api/v1")

@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

@app.get("/assets/{filename}")
def assets(filename: str):
    return FileResponse(os.path.join(FRONTEND_DIST, "assets", filename))
