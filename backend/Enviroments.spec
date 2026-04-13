import os

block_cipher = None

# working-directory: backend → cwd = backend/
# All paths are relative to the backend/ directory
FRONTEND_DIST = os.path.join("..", "frontend", "dist")  # ../frontend/dist

a = Analysis(
    ["app/main.py"],
    binaries=[],
    datas=[
        (FRONTEND_DIST, "frontend/dist"),
    ],
    hiddenimports=[
        "app.api.v1.routers.servers",
        "app.api.v1.routers.files",
        "app.models.server",
        "app.core.database",
        "infrastructure.ssh_client",
        "infrastructure.sftp_client",
        "uvicorn",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "fastapi.applications",
        "fastapi.routing",
        "sqlalchemy",
        "sqlalchemy.orm",
        "pydantic",
        "paramiko",
        "aiosqlite",
    ],
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Enviroments",
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Enviroments",
)
