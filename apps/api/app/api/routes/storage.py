from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response

_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".p2l": "application/json",
}

_STORAGE_PREFIXES = ("originals/", "masked/", "scene/", "exports/", "assets/")


def build_storage_router() -> APIRouter:
    """Serves stored blobs (masked cutouts, exports) by key.

    Storage resolves from app state at request time so the router can be
    registered before lifespan populates the services. Keys are validated
    against an allow-list of prefixes and reject traversal.
    """
    router = APIRouter(prefix="/api/storage", tags=["storage"])

    @router.get("/{key:path}")
    async def get_stored(key: str, request: Request) -> Response:
        if not any(key.startswith(prefix) for prefix in _STORAGE_PREFIXES):
            return Response(content=b"", status_code=404)
        if ".." in key or "\x00" in key:
            return Response(content=b"", status_code=404)
        storage = request.app.state.upload_service.storage
        data = await storage.get(key)
        if data is None:
            return Response(content=b"", status_code=404)
        return Response(content=data, media_type=_content_type(key))

    return router


def _content_type(key: str) -> str:
    lower = key.lower()
    for suffix, mime in _CONTENT_TYPES.items():
        if lower.endswith(suffix):
            return mime
    return "application/octet-stream"