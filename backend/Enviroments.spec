import os

block_cipher = None

# Working directory: backend/
# All paths are relative to the backend directory.
FRONTEND_DIST = os.path.join("..", "frontend", "dist")

a = Analysis(
    ["app/main.py"],
    binaries=[],
    datas=[
        (FRONTEND_DIST, "frontend/dist"),
    ],
    hiddenimports=[
        "app.api.v1.routers.auth",
        "app.api.v1.routers.files",
        "app.api.v1.routers.logs",
        "app.api.v1.routers.servers",
        "app.api.v1.routers.switches",
        "app.api.v1.routers.terminal",
        "app.core.auth",
        "app.core.database",
        "app.core.scheduler",
        "app.models.server",
        "app.models.server_favorite",
        "app.models.switch",
        "app.models.user",
        "infrastructure.sftp_client",
        "infrastructure.ssh_client",
        "infrastructure.ssh_worker",
        "uvicorn",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "fastapi",
        "fastapi.applications",
        "fastapi.routing",
        "sqlalchemy",
        "sqlalchemy.orm",
        "pydantic",
        "paramiko",
    ],
)

# Linux targets should use the deployment system's libgcc. Bundling a libgcc
# from the build image can accidentally raise the required GLIBC version.
a.binaries = [
    item for item in a.binaries
    if os.path.basename(item[0]) != "libgcc_s.so.1"
]

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
