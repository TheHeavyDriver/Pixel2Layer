# Pixel2Layer

Pixel-perfect SVG reconstruction of any artwork. Upload a PNG/JPG, and Pixel2Layer segments the image into editable vector layers, gradients, text, and image regions — right in the browser.

## Features

- **Upload & reconstruct** — drop in an image and get a layered scene graph back
- **Layered editor** — canvas-based editor with vector (SVG path), shape, text, and image layers; full transform/arrange/alignment controls
- **Progressive routing** — simple logos take the fast vector path, complex photos get masked region segmentation
- **Confidence scoring** — per-element confidence badges plus an overall reconstruction summary
- **Image tools** — background removal, filters (brightness, contrast, saturation, grayscale, invert, blur), and region editing (detect, crop, keep, cut) on segmented regions
- **Smart layer grouping** — one-click grouping of headers, hero sections, products, and decorations
- **Export** — PNG, JPEG, SVG, and PDF
- **Sharing & templates** — shareable editable links, template gallery, batch processing

## Architecture

| Package | Description |
|---------|-------------|
| `apps/api` | FastAPI backend: upload, reconstruction jobs (Redis + worker), storage, tools (`/api/tools`), sharing, templates, export |
| `apps/web` | Next.js 16 + React 19 + Fabric v7 editor |
| `packages/schema` | Shared TypeScript scene-graph schema (mirrored by pydantic models in the API) |

## Getting started

### Backend

```bash
cd apps/api
python -m venv .venv
.venv/bin/pip install -e .[dev]
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Storage defaults to the local backend (`apps/api/data/storage`) and the job queue to the in-memory backend; set `REDIS_URL` for shared/durable queues. Storage is abstracted behind `StorageBackend` so it can be swapped (e.g. S3/Supabase) without schema changes.

### Web

```bash
cd apps/web
npm install
npm run dev
```

The web app calls the API at `http://localhost:8000` by default (override with `NEXT_PUBLIC_API_BASE_URL`).

## Test

```bash
cd apps/api && .venv/bin/python -m pytest -q && .venv/bin/ruff check .
cd apps/web && npm test && npm run typecheck
```

## Roadmap

See [roadmap.md](roadmap.md) for the phased plan (v0.1→v0.5 done, plus a prioritized post-MVP backlog).

## License

Free and open source.