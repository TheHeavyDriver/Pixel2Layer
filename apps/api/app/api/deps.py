from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.services.auth import decode_access_token
from app.services.job_queue import JobQueue
from app.services.store import Store, User
from app.services.upload_service import UploadService


def get_upload_service(request: Request) -> UploadService:
    return request.app.state.upload_service


def get_job_queue(request: Request) -> JobQueue:
    return request.app.state.job_queue


def get_store(request: Request) -> Store:
    return request.app.state.store


def _auth_settings() -> Settings:
    return get_settings()


async def get_current_user(
    store: Annotated[Store, Depends(get_store)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve the authenticated user from a `Authorization: Bearer <jwt>` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    settings = _auth_settings()
    user_id = decode_access_token(
        token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await store.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]
JobQueueDep = Annotated[JobQueue, Depends(get_job_queue)]
StoreDep = Annotated[Store, Depends(get_store)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]