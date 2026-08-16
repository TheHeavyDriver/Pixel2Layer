from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.routes import export, jobs, upload
from app.core.config import Settings, get_settings
from app.services.job_queue import JobQueue, build_repository
from app.services.pipeline_worker import build_worker
from app.services.upload_service import UploadService, build_storage


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    jobBackend: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    storage = build_storage(settings)
    app.state.upload_service = UploadService(storage, settings)
    app.state.job_queue = JobQueue(
        build_repository(settings), settings, worker_impl=build_worker(storage)
    )
    app.state.job_queue.start()
    try:
        yield
    finally:
        await app.state.job_queue.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is not None:
        import app.core.config as cfg

        cfg._settings_override = settings  # type: ignore[attr-defined]

    app = FastAPI(
        title="Pixel2Layer API",
        version="0.1.0",
        lifespan=lifespan,
    )

    s = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(upload.router)
    app.include_router(jobs.router)
    app.include_router(export.router)

    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            app=s.app_name,
            environment=s.environment,
            jobBackend=s.job_backend,
        )

    return app


app = create_app()