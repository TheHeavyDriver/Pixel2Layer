from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from app.services.job_queue import Job
from app.services.pipeline import ReconstructionPipeline
from app.services.storage import StorageBackend

# Stages the worker reports to the queue; used to derive overall progress.
PIPELINE_STAGES = ["uploading", "analyzing", "text", "shapes", "colors", "building"]


def build_worker(storage: StorageBackend):
    """Factory for a JobQueue worker that runs the reconstruction pipeline."""
    pipeline = ReconstructionPipeline(storage=storage)

    async def work(
        job: Job,
        progress: Callable[[str, float, float | None], Awaitable[None]],
    ) -> dict:
        original_key = await _resolve_original(storage, job.upload_id)
        original = await storage.get(original_key)
        if original is None:
            raise FileNotFoundError(
                f"original upload {job.upload_id} not found in storage"
            )

        result = await pipeline.run(original, job.upload_id, progress)
        # Persist the scene graph result for fetch-by-id.
        await storage.put(
            f"scene/{job.id}.json",
            json.dumps(result.scene_graph).encode("utf-8"),
            "application/json",
        )
        return {
            "scene": result.scene_graph,
            "upload_id": result.upload_id,
            "original_url": result.original_url,
        }

    return work


async def _resolve_original(storage: StorageBackend, upload_id: str) -> str:
    candidates = await storage.list_files(f"originals/{upload_id}")
    if not candidates:
        raise FileNotFoundError(f"original upload {upload_id} not found in storage")
    return sorted(candidates)[0]