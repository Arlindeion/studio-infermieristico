"""Private filesystem helpers for PAZ-A2 plan/report artifacts.

This module contains no patient-domain logic. It deliberately works with bytes
and JSON-compatible mappings only, so security properties around file creation,
permissions, symlink handling and atomic replacement can be tested in isolation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import Any, Mapping
import uuid


MAX_ARTIFACT_FILE_BYTES = 4 * 1024 * 1024


class ArtifactSecurityError(Exception):
    """Raised when an A2 artifact cannot be handled safely."""


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _ensure_safe_destination(path: Path, overwrite: bool) -> None:
    if not path.parent.exists() or not path.parent.is_dir():
        raise ArtifactSecurityError("unsafe destination")
    try:
        existing = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode):
        raise ArtifactSecurityError("unsafe destination")
    if not overwrite:
        raise ArtifactSecurityError("destination exists")


def paths_equivalent(first: str | os.PathLike, second: str | os.PathLike) -> bool:
    """Return True when two artifact paths resolve to the same destination.

    ``Path.resolve(strict=False)`` also resolves existing symlink components.
    If both paths already exist, ``samefile`` provides a stronger inode check.
    """

    a = Path(first).expanduser()
    b = Path(second).expanduser()
    try:
        if a.exists() and b.exists() and os.path.samefile(a, b):
            return True
    except (OSError, RuntimeError):
        pass
    try:
        return a.resolve(strict=False) == b.resolve(strict=False)
    except (OSError, RuntimeError):
        return os.path.abspath(os.fspath(a)) == os.path.abspath(os.fspath(b))


def atomic_write_private_json(
    path: str | os.PathLike,
    payload: Mapping[str, Any],
    *,
    overwrite: bool = False,
    max_bytes: int = MAX_ARTIFACT_FILE_BYTES,
) -> None:
    destination = Path(path)
    _ensure_safe_destination(destination, overwrite)
    data = canonical_json_bytes(payload) + b"\n"
    if len(data) > max_bytes:
        raise ArtifactSecurityError("artifact too large")

    temp_name = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    fd: int | None = None
    try:
        fd = os.open(temp_name, flags, 0o600)
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        # Re-check after writing the temp file to avoid replacing a destination
        # created concurrently when overwrite was not requested.
        if not overwrite:
            try:
                os.lstat(destination)
            except FileNotFoundError:
                pass
            else:
                raise ArtifactSecurityError("destination exists")

        os.replace(temp_name, destination)
        try:
            dir_fd = os.open(destination.parent, os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        if fd is not None:
            os.close(fd)
        try:
            temp_name.unlink()
        except FileNotFoundError:
            pass


def read_private_json(
    path: str | os.PathLike,
    *,
    max_bytes: int = MAX_ARTIFACT_FILE_BYTES,
) -> dict[str, Any]:
    file_path = Path(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(file_path, flags)
    except OSError as exc:
        raise ArtifactSecurityError("cannot open artifact") from exc

    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ArtifactSecurityError("artifact is not regular")
        if os.name == "posix" and metadata.st_mode & 0o077:
            raise ArtifactSecurityError("artifact permissions too broad")
        if metadata.st_size > max_bytes:
            raise ArtifactSecurityError("artifact too large")

        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > max_bytes:
            raise ArtifactSecurityError("artifact too large")
    finally:
        os.close(fd)

    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactSecurityError("invalid artifact json") from exc
    if not isinstance(parsed, dict):
        raise ArtifactSecurityError("invalid artifact json")
    return parsed


def delete_private_file(path: str | os.PathLike) -> None:
    file_path = Path(path)
    try:
        metadata = os.lstat(file_path)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ArtifactSecurityError("unsafe artifact delete")
    file_path.unlink()
