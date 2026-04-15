import io
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.database import SessionLocal
from app.models.server import Server
from infrastructure.sftp_client import list_directory, download_file, upload_file, FileEntry

router = APIRouter(prefix="/servers/{server_id}/files", tags=["files"], dependencies=[Depends(get_current_user)])


# ── Request/Response models ────────────────────────────────────────────────────

class FileListResponse(BaseModel):
    path: str
    entries: list


class UploadRequest(BaseModel):
    path: str        # remote destination path (including filename)
    content: str     # base64 encoded


# ── GET  /servers/:id/files?path=... ──────────────────────────────────────────

@router.get("")
def list_files(server_id: int, path: str = "."):
    server = _get_server(server_id)

    try:
        entries = list_directory(
            ip=server.ip,
            port=server.port,
            username=server.ssh_username,
            password=server.ssh_password,
            key_file=server.ssh_key_file,
            remote_path=path,
        )
        return {
            "path": path,
            "entries": [e.__dict__ for e in entries],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SFTP error: {e}")


# ── GET  /servers/:id/files/download?path=... ──────────────────────────────────

@router.get("/download")
def download(server_id: int, path: str):
    server = _get_server(server_id)

    try:
        data = download_file(
            ip=server.ip,
            port=server.port,
            username=server.ssh_username,
            password=server.ssh_password,
            key_file=server.ssh_key_file,
            remote_path=path,
        )
        filename = path.split("/")[-1]
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Download error: {e}")


# ── POST  /servers/:id/files/upload ────────────────────────────────────────────

@router.post("")
def upload(server_id: int, payload: UploadRequest):
    import base64
    server = _get_server(server_id)

    try:
        content = base64.b64decode(payload.content)
        result = upload_file(
            ip=server.ip,
            port=server.port,
            username=server.ssh_username,
            password=server.ssh_password,
            key_file=server.ssh_key_file,
            remote_path=payload.path,
            content=content,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upload error: {e}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_server(server_id: int) -> Server:
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server
