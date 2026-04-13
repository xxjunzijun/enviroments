import os

block_cipher = None

# ── Paths ──────────────────────────────────────────────────────────────────────
# SPECPATH = directory containing the spec file = backend/
# SPECPATH is provided automatically by PyInstaller in spec file context
BACKEND_DIR  = os.path.dirname(os.path.abspath(SPECPATH))   # backend/
REPO_DIR     = os.path.dirname(BACKEND_DIR)                 # repo root
FRONTEND_DIR = os.path.join(REPO_DIR, "frontend", "dist")   # repo/frontend/dist

a = Analysis(
    [os.path.join(BACKEND_DIR, "app", "main.py")],
    binaries=[],
    datas=[
        (FRONTEND_DIR, "frontend/dist"),
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
