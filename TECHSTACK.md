# Pixel2Layer — Technologies, Libraries, Models, Output Formats & Languages

## Languages

| Language | Where |
|---|---|
| TypeScript | Frontend (`apps/web`), shared contract (`packages/schema`) |
| Python (≥ 3.11) | Backend (`apps/api`) |
| SQL (Postgres DDL) | Persistence (`apps/api` store + `docker-compose.yml`) |

## Frontend (`apps/web`)

| Technology / Library | Version | Purpose |
|---|---|---|
| Next.js (App Router, Turbopack) | ^16.3.1 | Web app framework (dev, build, SSR) |
| React + React DOM | ^19.0.0 | UI |
| Fabric.js (`fabric`) | ^7.4.0 | Canvas editor (layers, groups, viewport/zoom) |
| Tailwind CSS (+ `@tailwindcss/postcss`, `postcss`) | ^4.0.0 | Styling |
| TypeScript | ^5.5.0 | Type safety (`tsc --noEmit`) |
| Vitest (+ `jsdom`, `@testing-library/react`, `vitest-canvas-mock`) | ^4.1.10 | Unit tests |
| Playwright (`@playwright/test`) | ^1.62.1 | End-to-end tests (Chromium) |
| Node.js | ≥ 20 | Runtime / monorepo workspaces (`apps/*`, `packages/*`) |

## Backend (`apps/api`)

| Technology / Library | Version | Purpose |
|---|---|---|
| FastAPI (+ `fastapi[standard]`) | ≥ 0.115 | REST API + SSE progress streams |
| Uvicorn (`uvicorn[standard]`) | ≥ 0.30 | ASGI server |
| Pydantic (+ `pydantic-settings`) | ≥ 2.8 | Scene-graph schemas, config |
| `python-multipart` | — | Image/file uploads |
| OpenCV (`opencv-python-headless`) | ≥ 5.0.0.93 | Shape detection, segmentation, GrabCut, vectorizer, text morphology |
| NumPy | ≥ 2.4.6 | Image array math |
| Pillow | ≥ 10.4 | Rasterize PNG/JPG/PDF export, cutout encoding |
| scikit-image | ≥ 0.26.0 | Image utilities |
| scikit-learn | ≥ 1.9.0 | Color clustering (palette extraction) |
| Redis (`redis` lib + Redis 7, `docker-compose.yml`) | ≥ 5.0 | Job queue backend (alt: in-memory) |
| Postgres 16 (`asyncpg` + Postgres 16-alpine, host port 5434) | ≥ 0.30 (driver) | Users / projects / versions / shares / templates (alt: in-memory) |
| PyJWT | ≥ 2.8 | Auth (JWT) + PBKDF2 password hashing |
| `httpx` | ≥ 0.27 | API tests (dev) |
| pytest + pytest-asyncio | ≥ 8.3 | Backend tests (dev) |
| Ruff | ≥ 0.6 | Lint (dev) |
| uv | — | Python package/project manager (`.venv`) |

## Models (ML / vision)

| Model / Engine | Status | Purpose |
|---|---|---|
| VisionSegmenter (OpenCV: border-color separation → Otsu → GrabCut) | Built-in default | Foreground segmentation → masked cutout layers |
| ShapeDetector (OpenCV contours) | Built-in | Rectangle / circle / ellipse / line / polygon detection |
| Vectorizer (OpenCV contour → SVG path tracing) | Built-in | Irregular-blob → editable vector paths |
| VisionTextDetector (morphology + glyph validation; pluggable OCR interface: PaddleOCR / Tesseract / EasyOCR) | Built-in (OCR optional) | Text-region detection |
| FontMatcher (render-and-compare ink-silhouette IoU over a curated font registry resolved via fontconfig) | Built-in | OCR font family/weight matching |
| SAM 2 + LoRA (`sam2`, `torch`, `torchvision` — `[train]` extra) | Optional | Fine-tuned segmentation backend when `SAM2_LORA_WEIGHTS` is set; graceful fallback to VisionSegmenter |

## Output / Exchange Formats

| Format | Producer | Notes |
|---|---|---|
| PNG (`image/png`) | API export, cutout storage | Raster export + masked layers under `/api/storage/…` |
| JPG (`image/jpeg`) | API export | Raster export |
| SVG (`image/svg+xml`) | API export, vectorizer | Vector export; scene vector paths use `fill-rule="evenodd"` |
| PDF (`application/pdf`) | API export (Pillow) | Document export |
| `.p2l` (JSON scene-graph envelope) | API save/load | Project save / reopen (`.p2l`, `application/json`); versioned by `schemaVersion` |
| SSE (`text/event-stream`) | API `/api/jobs/{id}/events` | `update` + terminal `done` events for reconstruction progress |
| Upload inputs | Web upload modal | PNG, JPG/JPEG, WebP (≤ 25 MB) |

## Shared Contract

| Package | Contents |
|---|---|
| `@pixel2layer/schema` (`packages/schema`, TS) | `SceneGraphSchema` — canvas, layers (rectangle/circle/ellipse/line/polygon/vector/text/image), transforms, filters, confidence; mirrored by Pydantic models in `apps/api/app/schemas/` |

## Infrastructure

- Docker Compose: Postgres 16-alpine + Redis 7-alpine (ports 5434 / 6379)
- Monorepo: npm workspaces (`apps/*`, `packages/*`); Python managed with `uv`
