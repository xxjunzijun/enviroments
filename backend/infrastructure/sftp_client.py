"""
Infrastructure Layer - SFTP File Operations
Pure functions, no FastAPI dependency
"""

import os
import io
import paramiko
from dataclasses import dataclass
from typing import Optional


@dataclass
class FileEntry:
    name: str
    path: str
    type: str        # "file" or "directory"
    size: Optional[int] = None   # bytes
    modified: Optional[str] = None


def sftp_connect(ip: str, port: int, username: str, password: Optional[str], key_file: Optional[str]):
    """Create and return an SFTP client."""
    transport = paramiko.Transport((ip, port))
    transport.connect(username=username, password=password, hostkey=None)
    sftp = paramiko.SFTPClient.from_transport(transport)
    return sftp


def list_directory(
    ip: str,
    port: int,
    username: str,
    password: Optional[str],
    key_file: Optional[str],
    remote_path: str = ".",
) -> list[FileEntry]:
    """
    List directory contents via SFTP.
    Returns list of FileEntry sorted: directories first, then files, alphabetically.
    Normalizes all paths to forward slashes.
    """
    client = sftp_connect(ip, port, username, password, key_file)
    entries = []
    try:
        # Normalize remote_path to forward slashes
        normalized = remote_path.replace("\\", "/")
        # Keep "/" as root; strip trailing "/" for other paths
        if normalized == "/":
            remote_path = "/"
        elif normalized == "." or normalized == "":
            remote_path = "."
        else:
            remote_path = normalized.rstrip("/")

        # List the target directory
        target = remote_path if remote_path != "." else "."
        names = client.listdir(target)

        for name in names:
            # Build full path: root "/" + name, or current dir + name
            if remote_path == "/":
                full_path = "/" + name
            elif remote_path == ".":
                full_path = name
            elif remote_path.endswith("/"):
                full_path = remote_path + name
            else:
                full_path = remote_path + "/" + name

            try:
                stat_result = client.stat(full_path)
                is_dir = False
                try:
                    is_dir = stat_result.isdir()
                except Exception:
                    # Fallback: try to listdir the path
                    try:
                        client.listdir(full_path)
                        is_dir = True
                    except Exception:
                        is_dir = False

                entry_type = "directory" if is_dir else "file"
                size = None
                if entry_type == "file":
                    try:
                        size = stat_result.st_size
                    except Exception:
                        pass

                entries.append(FileEntry(
                    name=name,
                    path=full_path,
                    type=entry_type,
                    size=size,
                    modified=str(stat_result.st_mtime) if hasattr(stat_result, 'st_mtime') else None,
                ))
            except Exception as e:
                # Show as file with unknown type
                entries.append(FileEntry(
                    name=name,
                    path=full_path,
                    type="file",
                    size=None,
                    modified=None,
                ))
    finally:
        client.close()

    # Sort: directories first, then files, alphabetical
    entries.sort(key=lambda e: (0 if e.type == "directory" else 1, e.name.lower()))
    return entries


def download_file(
    ip: str,
    port: int,
    username: str,
    password: Optional[str],
    key_file: Optional[str],
    remote_path: str,
) -> bytes:
    """Download a file and return its bytes content."""
    client = sftp_connect(ip, port, username, password, key_file)
    try:
        return client.open(remote_path, "rb").read()
    finally:
        client.close()


def upload_file(
    ip: str,
    port: int,
    username: str,
    password: Optional[str],
    key_file: Optional[str],
    remote_path: str,
    content: bytes,
) -> dict:
    """Upload a file. Creates parent directories if needed. Returns result dict."""
    client = sftp_connect(ip, port, username, password, key_file)
    try:
        # Ensure parent directory exists
        parent = os.path.dirname(remote_path).replace("\\", "/")
        if parent and parent != ".":
            _mkdir_recursive(client, parent)

        # Write file
        client.open(remote_path, "wb").write(content)
        stat = client.stat(remote_path)
        return {"path": remote_path, "size": stat.st_size, "success": True}
    finally:
        client.close()


def create_directory(
    ip: str,
    port: int,
    username: str,
    password: Optional[str],
    key_file: Optional[str],
    remote_path: str,
) -> dict:
    """Create a directory recursively via SFTP."""
    client = sftp_connect(ip, port, username, password, key_file)
    try:
        normalized = (remote_path or "").replace("\\", "/").rstrip("/")
        if not normalized or normalized == ".":
            raise ValueError("Directory path is required")
        _mkdir_recursive(client, normalized)
        return {"path": normalized, "success": True}
    finally:
        client.close()


def _mkdir_recursive(sftp, path: str):
    """Create directory and all parents via SFTP if they don't exist."""
    dirs = []
    while path and path != "." and path != "/":
        try:
            sftp.stat(path)
            break
        except Exception:
            dirs.insert(0, os.path.basename(path))
            path = os.path.dirname(path).replace("\\", "/")
    for d in dirs:
        path = (path + "/" + d).replace("//", "/")
        try:
            sftp.mkdir(path)
        except Exception:
            pass   # Already exists


def get_home_directory(
    ip: str,
    port: int,
    username: str,
    password: Optional[str],
    key_file: Optional[str],
) -> str:
    """Get the user's home directory via SFTP."""
    client = sftp_connect(ip, port, username, password, key_file)
    try:
        return client.get_channel().recv(-1)  # Not reliable
    except Exception:
        pass
    finally:
        client.close()

    # Fallback: run remote command
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, port=port, username=username, password=password,
                    key_filename=key_file, timeout=10, look_for_keys=False)
        _stdin, stdout, _stderr = ssh.exec_command("echo $HOME", timeout=10)
        return stdout.read().decode().strip()
    finally:
        ssh.close()
