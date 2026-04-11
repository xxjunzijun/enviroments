import os
import sys

block_cipher = None
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))

a = Analysis(
    [os.path.join(project_root, "backend", "app", "main.py")],
    binaries=[],
    datas=[
        (os.path.join(project_root, "frontend", "dist"), "frontend/dist"),
    ],
    hiddenimports=[
        "app.api.v1.routers.servers",
        "app.models.server",
        "app.core.database",
        "infrastructure.ssh_client",
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
