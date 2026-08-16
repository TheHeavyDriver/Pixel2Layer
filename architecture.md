# Pixel2Layer — System Architecture

This document is the technical blueprint for the Pixel2Layer platform, derived from `description.md`, `prd.md`, and `roadmap.md`. It describes the topology, components, data flow, key contracts, and infra for phases v0.1 → v0.5 (and the seams for post-MVP work).

---

## 1. Architectural Overview

```text
                    ┌────────────────────────────────────────────┐
                    │              Web Browser                   │
                    │  Next.js App (React/TS/Tailwind)           │
                    │                                            │
                    │  CanvasEditor (Fabric.js)                  │
                    │  LayersPanel  PropertiesPanel  Dashboard   │
                    └───────────────┬────────────────────────────┘
                                    │ HTTPS (REST / SSE / upload)
                                    ▼
                    ┌────────────────────────────────────────────┐
                    │            FastAPI Backend                 │
                    │                                            │
                    │  Auth / ProjectService / ExportService     │
                    │  Upload → PipelineAPI (jobs)               │
                    └───────┬────────────────────────┬───────────┘
                            │ publish job            │ enqueue
                            ▼                        ▼
                     ┌──────────────┐        ┌──────────────────┐
                     │  Job Queue / │        │  Worker(s)       │
                     │  Broker      │        │  (reconstruction)│
                     └──────┬───────┘        └────────┬─────────┘
                            │                         │
                            ▼                         ▼
                   ┌──────────────────────────────────────────────┐
                   │         Reconstruction Pipeline              │
                   │  TextDetector  ShapeDetector  ColorExtractor │
                   │  Segmenter(SAM2) Vectorizer                  │
                   │              │                               │
                   │              ▼                               │
                   │  SceneGraphBuilder ──► ConfidenceScorer       │
                   └───────┬──────────────────────────────┬───────┘
                           │ scene graph JSON             │ cutouts/masks
                           ▼                              ▼
                  ┌─────────────────┐            ┌─────────────────┐
                  │  PostgreSQL     │            │ Supabase Storage│
                  │  projects, jobs,│            │ originals, cut- │
                  │  versions,      │            │ outs, exports,  │
                  │  templates,     │            │ assets, .p2l    │
                  │  shares, users  │            │ files           │
                  └─────────────────┘            └─────────────────┘
```

---

## 2. Deployment Topology

| Surface | Runtime | Host | Responsibilities |
|---------|---------|------|------------------|
| `apps/web` | Next.js (React, TS, Tailwind) | Vercel | Editor UI, dashboard, auth pages, SSR/metadata, SSE listening |
| `apps/api` | FastAPI (Python) | Render / Railway / AWS ECS | REST API, auth, project/export services, job orchestration API |
| Worker | Python (celery/arq/RQ) | Render worker / EC2 / same host as API for v0.1 | Executes reconstruction jobs |
| Broker | Redis | Upstash / Render Redis | Job queue + SSE pub/sub + result cache |
| Postgres | Supabase Postgres | Supabase | Persistent relational data (users, projects, versions, templates, shares, jobs) |
| Storage | Supabase Storage | Supabase | Binary blobs (images, cutouts, exports, `.p2l`) |
| External ML | SAM 2, OCR models | Worker process / model inference service | Heavy CV/ML inference |

**v0.1 note:** API + worker may run on a single host with Redis as the broker; the split happens when model startup cost demands dedicated workers.

---

## 3. Components in Detail

### 3.1 Frontend (`apps/web`)

- **CanvasEditor** — Fabric.js canvas rendering the scene graph. Owns selection, transforms (move/resize/rotate), grouping, align/distribute, undo/redo, and rendering fidelity per element type. Vector paths render as Fabric paths; photographs render as `fabric.Image` with optional masks.
- **LayersPanel** — tree of scene-graph layers; select/hide/lock/reorder/rename/duplicate/delete operations map to scene graph mutations.
- **PropertiesPanel** — schema-driven form: each element type (text/shape/image/vector) exposes its editable property set via the SceneGraphSchema; the panel renders from the schema so new types are cheap to add.
- **Dashboard / ProjectScreen** — auth flows, project list, templates, sharing UI, batch upload status.
- **Client state** — scene graph held in a single source of truth (React state/Zustand), synced to Fabric objects; undo/redo operates on scene graph snapshots, not DOM.

### 3.2 API (`apps/api`)

- **Upload** → validates, stores original in Supabase Storage, creates a job row.
- **Pipelines** → creates `/jobs/{id}`; client polls or subscribes to SSE for progress; on completion returns the scene graph (possibly fetched directly from storage).
- **ProjectService** → CRUD over Postgres; version snapshots; share links with view/edit scope; template gallery; batch group tracking.
- **ExportService** → server-side rasterization of the scene graph to PNG/JPG/SVG/PDF; stores result in Storage; `.p2l` serialization/deserialization.
- **Auth** → Supabase Auth integration for email/OAuth; JWT-based bearer for data access.

### 3.3 Worker & Reconstruction Pipeline

Each worker consumes jobs and runs the pipeline:

```text
load original ─► TextDetector ─► ShapeDetector ─► ColorExtractor
                    │                │                 │
                    ├────────────►  detect elements ◄───┤
                    ▼                ▼                 ▼
        text objects      geometric objects       fill/stroke props
                    │                │                 │
                    ├────────────►  Segmenter(SAM2) ◄──┤   (advanced passes)
                    ▼                ▼                 ▼
              masked regions        │            vector paths
              (photographs)  ───────┼────────── (Vectorizer)
                                    ▼
                    SceneGraphBuilder (order/layers) ─► ConfidenceScorer
                                    ▼
                          scene graph JSON ─► Storage / DB
```

Processing order guarantees: geometric and text elements resolve first; vectorization and segmentation are later, heavier passes. The pipeline is composable so stages can be toggled per job (e.g., "skip segmentation") and added incrementally (v0.2 text+shapes, v0.4 vectorization+segmentation).

### 3.4 Data Stores

- **Postgres tables:** `users`, `projects`, `versions`, `shares`, `templates`, `jobs`. Scene graph body stored as JSONB on `projects` (with an `assets` reference to Storage for cutouts/originals).
- **Supabase Storage buckets:** `originals/`, `cutouts/`, `exports/`, `projects/` (`.p2l`), `assets/`.

---

## 4. Shared Contracts (Key For Both Sides)

### 4.1 SceneGraphSchema — canonical document & API contract

- Element types: `text`, `rectangle`, `circle`, `ellipse`, `line`, `polygon`, `path/vector`, `image`.
- Every element carries: id, type, transform (x, y, scale, rotation), fill/stroke/opacity, layer order, and `confidence`.
- Canvas metadata: width/height, background.
- `.p2l` format = scene graph **superset**: adds assets (cutouts/originals), typography refs, editor metadata (camera view, selection memory).
- Versioned (v1, ...); frontend rendering and backend reconstruction both depend on it.

### 4.2 API surface (high level)

```text
POST   /api/upload                     → { uploadId, presignedUrl }   then PUT to storage
POST   /api/jobs                       → { jobId }                    (from uploadId)
GET    /api/jobs/{id}                  → { status, stage, progress, result? }
GET    /api/jobs/{id}/events(SSE)      → stream of stage/progress updates
POST   /api/projects            (auth) → create from scene graph / .p2l
GET    /api/projects            (auth) → list
GET    /api/projects/{id}       (auth) → scene graph + metadata
PATCH  /api/projects/{id}       (auth) → update scene graph (auto-save)
POST   /api/projects/{id}/versions (auth)
GET    /api/projects/{id}/versions (auth)
POST   /api/projects/{id}/share  (auth) → create token
GET    /api/share/{token}                → view / edit (reads share scope)
POST   /api/templates    (auth) → save reconstructed design as template
GET    /api/templates                → gallery
POST   /api/export   (auth) → { projectId, format }  →  presignedUrl to export
POST   /api/batches   (auth) → { uploadIds[] } → { batchId }  (Phase 4)
```

### 4.3 Async protocol

- Job lifecycle: `queued → running → done | failed`; stages `uploading → analyzing → text → shapes → colors → segmenting → vectorizing → building → exporting`.
- Client communicates progress via SSE; jobs are retried on worker failure with backoff.

---

## 5. Cross-Cutting Concerns

- **Confidence as data, not flavor** — every element stores `confidence` end to end; UI badges and overall score consume the same field. Confidence is generated in `ConfidenceScorer` and never dropped.
- **Deterministic editor** — AI/CV only ever appears at import time; all editor interactions are direct scene graph mutations. No prompt-based editing path exists.
- **Security** — auth on all mutating endpoints; share links scope to the token's view/edit permission; storage buckets are private with signed URLs; secrets live in the platform env store.
- **Observability** — job stage durations, failure rates, model latencies, reconstruction accuracy (golden fixtures) tracked per version.

---

## 6. Testing & Verification Mapping

- Unit/integration tests (as prescribed in PRD Testing Decisions) at module boundaries: ShapeDetector, ColorExtractor, SceneGraphBuilder, JobQueue, ProjectService, SceneGraphSchema, ExportService.
- Backend tests: `pytest` with fixture images and golden-file scene graphs; Testcontainers Postgres (or SQLite in-memory for unit-level).
- Frontend: e2e tests over Fabric behavior; schema validated against SceneGraphSchema.
- CI gate: schema-compat tests ensure the frontend/backend never disagree on the contract.

---

## 7. Scaling & Extension Seams (Post-MVP)

- **Live collaboration** — scene graph is already a natural CRDT candidate; add a sync layer and op log later.
- **More element types / design system** — the schema-driven PropertiesPanel makes adding types cheap; add `components`/`auto-layout` as new node types.
- **Faster reconstruction** — model inference can move to a dedicated GPU service without touching the pipeline interface.
- **Multi-tenancy / team workspaces** — add `team_id` and policies to existing tables.

---

## 8. Architecture Decision Records (Summary)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Canvas | Fabric.js | Mature scene graph + manipulation controls + serialization, out-of-the-box for the MVP |
| Backend | FastAPI (Python) | Native fit for OpenCV/Pillow/NumPy/SAM2/OCR ecosystem |
| Storage/DB/Auth | Supabase (Postgres + Storage + Auth) | Managed Postgres + CDN-backed blobs + auth out of the box |
| Async | Redis-backed job queue + SSE | Cheap, shippable at v0.1; scales to separate worker fleet later |
| Photo handling | SAM 2 segmentation, labeled approximate | Honest about unrecoverable information in flat images |
| Text handling | Editable text; vector-outline fallback | Preserves fidelity when font matching is uncertain |
| Shared contract | Versioned SceneGraphSchema | Both sides depend on it; keeps frontend/backend in lockstep |