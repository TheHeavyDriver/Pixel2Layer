# Pixel2Layer

Pixel-perfect SVG reconstruction of any artwork. Upload a PNG/JPG, and Pixel2Layer segments the image into editable vector layers, gradients, text, and image regions — right in the browser.

## Features

- **Upload & reconstruct** — drop in an image and get a layered scene graph back
- **Layered editor** — canvas-based editor with vector (SVG path), shape, text, and image layers; full transform/arrange/alignment controls
- **Progressive routing** — simple logos take the fast vector path, complex photos get masked region segmentation
- **Confidence scoring** — per-element confidence badges plus an overall reconstruction summary
- **Font matching** — OCR text is matched against an expanded font database by comparing rendered glyph silhouettes, so detected type stays editable (family, weight, and a silhouette-IoU score in the confidence note)
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

## SAM 2 fine-tuning (optional)

The default segmenter is a lightweight OpenCV `VisionSegmenter`. For better
design-graphic segmentation, Pixel2Layer can LoRA-fine-tune [Segment Anything 2](https://github.com/facebookresearch/sam2)
and use the fine-tuned model at runtime (falls back to OpenCV if weights or
deps are missing):

```bash
# 1. Heavy deps (torch + sam2) in a separate venv
cd apps/api
python -m venv .venv-train
.venv-train/bin/pip install -e '.[train]'

# 2. Drop design-graphic images (logos, posters) into data/finetune/raw and
#    build a pseudo-label dataset from the pipeline's own segmentation output
.venv-train/bin/python -m app.services.finetune.train prepare \
  --raw data/finetune/raw --dataset data/finetune/datasets --name design-graphics

# 3. Download a stock SAM 2 checkpoint (e.g. sam2.1_hiera_small.pt) into
#    data/finetune/weights, then fine-tune (exports only the small LoRA weights)
.venv-train/bin/python -m app.services.finetune.train train \
  --dataset data/finetune/datasets/design-graphics \
  --checkpoint data/finetune/weights/sam2.1_hiera_small.pt \
  --out data/finetune/weights/lora-mask-sam2.pt

# 4. Enable it for the API
#    SAM2_LORA_WEIGHTS=data/finetune/weights/lora-mask-sam2.pt
```

Runtime integration lives in `apps/api/app/services/finetune/sam2_segmenter.py`;
the training CLI is `apps/api/app/services/finetune/train.py`. When
`SAM2_LORA_WEIGHTS` is unset, unavailable, or the `[train]` extras are not
installed, the pipeline transparently keeps using `VisionSegmenter`.

## Font matching

`apps/api/app/services/fonts/` holds an expanded font database and the matcher
that reconstructs editable typography from OCR text:

- **Database** — `registry.py` curates open-license families across
  sans/serif/mono/display categories and resolves each to a real TTF/OTF file
  via fontconfig (bundled fonts optional). Missing fonts degrade gracefully.
- **Matcher** — `matching.py` renders the OCR content in each candidate family
  at the detected size and ranks families by ink-silhouette IoU. Regular-vs-bold
  is decided per family, light-on-dark text is handled, and the top match's
  score becomes a `font 'Name' matched (score 0.9x)` confidence note.
- **Wiring** — `ReconstructionPipeline` runs the matcher after text detection;
  the scene graph's `fontFamily`/`fontWeight`/`fontStyle` are filled from the
  match, PNG/PDF export renders with the resolved font, and `ConfidenceScorer`
  weights the note's score into the per-text confidence.

## Roadmap

See [roadmap.md](roadmap.md) for the phased plan (v0.1→v0.5 done, plus a prioritized post-MVP backlog).

## License

Free and open source.