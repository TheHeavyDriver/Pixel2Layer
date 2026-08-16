from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.config import Settings
from app.services.storage import LocalStorage
from app.services.upload_service import (
    InvalidUploadError,
    UploadService,
    UploadTooLargeError,
)


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        storage_dir=tmp_path / "storage",
        job_backend="memory",
        environment="test",
    )


@pytest.fixture()
def service(settings: Settings) -> UploadService:
    storage = LocalStorage(settings.storage_dir)
    return UploadService(storage, settings)


def _upload(content: bytes, content_type: str, filename: str = "img.png") -> UploadFile:
    headers = {
        "content-type": content_type,
        "content-disposition": f'inline; filename="{filename}"',
    }
    return UploadFile(
        filename=filename, headers=Headers(dict(headers)), file=io.BytesIO(content)
    )


async def test_store_png(service: UploadService) -> None:
    result = await service.store(_upload(b"\x89PNG\r\n\x1a\nfakedata", "image/png"))
    assert result.extension == "png"
    assert result.content_type == "image/png"
    assert result.key.startswith("originals/")
    assert result.key.endswith(".png")
    assert len(result.sha256) == 64
    assert (service.storage.root / result.key).read_bytes().startswith(b"\x89PNG")


async def test_store_jpeg_and_webp(service: UploadService) -> None:
    jpg = await service.store(_upload(b"jpegdata", "image/jpeg", "a.jpg"))
    assert jpg.extension == "jpg"
    webp = await service.store(_upload(b"webpdata", "image/webp", "b.webp"))
    assert webp.extension == "webp"


async def test_reject_unsupported_type(service: UploadService) -> None:
    with pytest.raises(InvalidUploadError):
        await service.store(_upload(b"gifdata", "image/gif", "x.gif"))


async def test_reject_empty_file(service: UploadService) -> None:
    with pytest.raises(InvalidUploadError):
        await service.store(_upload(b"", "image/png"))


async def test_reject_too_large(settings: Settings, tmp_path: Path) -> None:
    s = Settings(storage_dir=tmp_path / "s", max_upload_bytes=8, environment="test")
    service = UploadService(LocalStorage(s.storage_dir), s)
    with pytest.raises(UploadTooLargeError):
        await service.store(_upload(b"this is more than eight bytes", "image/png"))


async def test_local_storage_prevents_traversal(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "root")
    with pytest.raises(ValueError):
        await storage.put("../../escape.txt", b"x", "text/plain")