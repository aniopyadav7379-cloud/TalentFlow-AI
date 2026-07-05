"""
File storage for uploaded resumes.

`StorageBackend` is the interface every caller depends on. `LocalStorage`
backs it with the filesystem (default, good for dev/tests). An S3-backed
implementation can be dropped in later behind the same interface without
touching any calling code — `get_storage_backend()` is the only place that
needs to change.
"""
from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings


def _safe_filename(candidate_id: str, original_filename: str) -> str:
    """Prevent path traversal / collisions: sanitize name, prefix with a UUID."""
    stem = Path(original_filename).stem
    suffix = Path(original_filename).suffix
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)[:80]
    safe_suffix = re.sub(r"[^a-zA-Z0-9.]", "", suffix)[:10] or ".pdf"
    return f"{candidate_id}/{uuid.uuid4().hex}_{safe_stem}{safe_suffix}"


class StorageBackend(ABC):
    @abstractmethod
    def save(self, candidate_id: str, filename: str, content: bytes) -> str:
        """Persist file content, return a URL/path that `read` can later resolve."""

    @abstractmethod
    def read(self, file_url: str) -> bytes:
        """Return the raw bytes for a previously-saved file."""

    @abstractmethod
    def exists(self, file_url: str) -> bool:
        ...


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or get_settings().LOCAL_STORAGE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, candidate_id: str, filename: str, content: bytes) -> str:
        if not content:
            raise ValueError("Cannot save an empty file")
        relative_path = _safe_filename(candidate_id, filename)
        full_path = self.base_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return f"local://{relative_path}"

    def _resolve(self, file_url: str) -> Path:
        if not file_url.startswith("local://"):
            raise ValueError(f"LocalStorage cannot resolve URL scheme: {file_url}")
        relative_path = file_url.removeprefix("local://")
        resolved = (self.base_dir / relative_path).resolve()
        # Guard against path traversal escaping base_dir.
        if self.base_dir.resolve() not in resolved.parents and resolved != self.base_dir.resolve():
            raise ValueError("Resolved path escapes storage base directory")
        return resolved

    def read(self, file_url: str) -> bytes:
        path = self._resolve(file_url)
        if not path.exists():
            raise FileNotFoundError(f"No file at {file_url}")
        return path.read_bytes()

    def exists(self, file_url: str) -> bool:
        try:
            return self._resolve(file_url).exists()
        except ValueError:
            return False


def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.STORAGE_BACKEND == "local":
        return LocalStorage()
    raise NotImplementedError(
        f"Storage backend '{settings.STORAGE_BACKEND}' is not implemented yet. "
        "Add an S3Storage(StorageBackend) class and register it here."
    )
