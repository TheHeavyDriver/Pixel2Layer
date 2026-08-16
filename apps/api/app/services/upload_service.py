from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from fastapi import UploadFile

from app.core.config import Settings
from app.services.storage import LocalStorage, StorageBackend

ALLOWED_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


class InvalidUploadError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


@dataclass
class UploadResult:
    upload_id: str
    key: str
    url: str
    content_type: str
    extension: str
    size_bytes: int
    sha256: str


class UploadService:
    """Validates uploads (type, size) and stores the original blob."""

    def __init__(self, storage: StorageBackend, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings

    async def store(self, file: UploadFile) -> UploadResult:
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_EXTENSIONS:
            raise InvalidUploadError(
                f"Unsupported type '{content_type}'. Supported: PNG, JPG/JPEG, WebP."
            )

        data = await file.read()
        if len(data) == 0:
            raise InvalidUploadError("Empty file uploaded.")

        if len(data) > self.settings.max_upload_bytes:
            raise UploadTooLargeError(
                f"File is {len(data)} bytes; limit is {self.settings.max_upload_bytes} bytes."
            )

        digest = hashlib.sha256(data).hexdigest()
        upload_id = uuid.uuid4().hex
        extension = ALLOWED_EXTENSIONS[content_type]
        key = f"originals/{upload_id}.{extension}"

        stored = await self.storage.put(key, data, content_type)

        return UploadResult(
            upload_id=upload_id,
            key=stored.key,
            url=stored.url,
            content_type=content_type,
            extension=extension,
            size_bytes=stored.size_bytes,
            sha256=digest,
        )


def build_storage(settings: Settings) -> StorageBackend:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_dir)
    raise NotImplementedError("supabase storage backend not yet implemented")