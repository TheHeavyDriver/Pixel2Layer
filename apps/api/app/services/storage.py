from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StoredObject:
    key: str
    url: str
    size_bytes: int


class StorageBackend(ABC):
    """Blob storage for originals, cutouts, exports, and .p2l files."""

    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...

    @abstractmethod
    async def get(self, key: str) -> bytes | None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    async def list_files(self, prefix: str) -> list[str]:
        """Return object keys under a prefix (used to resolve extensioned keys)."""
        return []


class LocalStorage(StorageBackend):
    """Filesystem-backed storage for local dev / tests."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path_for(self, key: str) -> Path:
        # Prevent path traversal: normalize and ensure it stays under root.
        clean = Path(key)
        path = (self.root / clean).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"invalid storage key: {key}")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(key=key, url=str(path), size_bytes=len(data))

    async def get(self, key: str) -> bytes | None:
        path = self._path_for(key)
        return path.read_bytes() if path.exists() else None

    async def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            path.unlink()

    async def list_files(self, prefix: str) -> list[str]:
        root_resolved = self.root.resolve()
        base = (self.root / prefix).resolve()
        if not base.is_relative_to(root_resolved):
            raise ValueError(f"invalid prefix: {prefix}")
        matches: list[str] = []
        prefix_str = prefix
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.root))
            if rel.startswith(prefix_str):
                matches.append(rel)
        return sorted(matches)