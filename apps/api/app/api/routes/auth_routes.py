from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import CurrentUserDep, StoreDep
from app.core.config import get_settings
from app.services.auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.store import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


def _user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, name=user.name)


def _issue_token(user_id: str) -> str:
    settings = get_settings()
    return create_access_token(
        user_id,
        secret=settings.jwt_secret,
        expires_minutes=settings.jwt_expires_minutes,
        algorithm=settings.jwt_algorithm,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, store: StoreDep) -> AuthResponse:
    email = req.email.lower().strip()
    if await store.get_user_by_email(email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        )
    user = await store.create_user(
        email=email,
        password_hash=hash_password(req.password),
        name=req.name,
    )
    return AuthResponse(token=_issue_token(user.id), user=_user_response(user))


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, store: StoreDep) -> AuthResponse:
    user = await store.get_user_by_email(req.email.lower().strip())
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )
    return AuthResponse(token=_issue_token(user.id), user=_user_response(user))


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUserDep) -> UserResponse:
    return _user_response(user)