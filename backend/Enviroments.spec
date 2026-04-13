import os
import sys

block_cipher = None

# SPECPATH = backend/ directory (where this spec file lives)
project_root = SPECPATH  # backend/
frontend_dist = os.path.join(project_root, "..", "frontend", "dist")  # ../frontend/dist

a = Analysis(
    [os.path.join(project_root, "app", "main.py")],
    binaries=[],
    datas=[
        (frontend_dist, "frontend/dist"),
    ],
    hiddenimports=[
        "app.api.v1.routers.servers",
        "app.api.v1.routers.files",
        "app.models.server",
        "app.core.database",
        "infrastructure.ssh_client",
        "infrastructure.sftp_client",
        "uvicorn",
        "fastapi",
        "sqlalchemy",
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
