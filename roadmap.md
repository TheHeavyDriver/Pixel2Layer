# Pixel2Layer — Product Roadmap

Derived from `prd.md`. Each phase ships independently, in order. Milestones within a phase are listed in build order, and testing decisions are applied continuously (see PRD "Testing Decisions").

Legend: v0.1, v0.2 ... = internal milestone tags; 🔬 = deep module to write tests for; 🔒 = auth/access control.

---

## Phase 1 — Core MVP (v0.1 → v0.2)

Goal: upload an image and end up with a fully editable design in the browser — no accounts required yet.

### v0.1 — Foundations & pipeline shell
- [x] Scaffold monorepo: `apps/web` (Next.js + TS + Tailwind) and `apps/api` (FastAPI)
- [x] Stand up Supabase (Storage + Postgres) and local dev env / docker-compose
- [x] **SceneGraphSchema** 🔬 — canonical JSON schema for element types, properties, layering, canvas metadata
- [x] **UploadService** 🔬 — accept PNG/JPG/JPEG/WebP, validate, store original, return reference
- [x] **JobQueue** 🔬 — async job lifecycle (queued → running → done/failed), progress, retries, completion notification
- [x] File upload flow wired to job creation + progress display in the web app

### v0.2 — Reconstruction + editor
- [x] **TextDetector** 🔬 — OCR + font matching; editable text objects; vector-outline fallback when font confidence is low
- [x] **ShapeDetector** 🔬 — circles, ellipses, rectangles, rounded rects, lines, polygons
- [x] **ColorExtractor** 🔬 — dominant colors + gradients per region
- [x] **SceneGraphBuilder** 🔬 — compose detected elements into ordered scene graph
- [x] **ExportService** — PNG / JPG / SVG export; `.p2l` save/load round-trip 🔬
- [x] **CanvasEditor** — Fabric.js canvas: select, move, resize, rotate, duplicate, delete, multi-select, group/ungroup, align/distribute; undo/redo
- [x] **LayersPanel** — select, hide/show, lock, reorder, rename, duplicate, delete
- [x] **PropertiesPanel** — text / shape / image property editing
- [x] Foundation of **ConfidenceScorer** — per-element confidence surfaced in the API model (full UI later in Phase 3)
- [x] e2e tests for the core editor flow

**Exit criteria:** user uploads a flat poster and edits its text, shape colors, and layout in the browser, then exports PNG/SVG and reopens the saved design.

---

## Phase 2 — Auth & Persistence (v0.3)

Goal: accounts and durable project library.

- [x] Auth — self-hosted email/password + JWT bearer (pluggable seam for Supabase Auth / OAuth later)
- [x] **ProjectService** 🔬 — project CRUD (create, rename, delete, list), scoped to the authenticated user 🔒
- [x] Cloud persistence of scene graphs and projects to Postgres (Postgres backend; Supabase Storage deferred)
- [x] **Version history** 🔬 — snapshot-based versioning per project; restore to earlier version
- [x] Project dashboard (list / open / delete / rename your projects)
- [x] First class `.p2l` save/load across sessions for logged-in users

**Exit criteria:** a signed-in user creates, edits, saves, reopens, and rolls back projects from any browser.

---

## Phase 3 — Vectorization, Segmentation & Confidence (v0.4)

Goal: handle logos/illustrations/photographs and make reconstruction quality transparent.

- [x] **Vectorizer** 🔬 — Potrace + OpenCV contours → SVG paths; path editing in the editor
- [x] **Segmenter** 🔬 — SAM 2 foreground/object segmentation → masked image layers, explicitly labeled approximate
- [x] **ConfidenceScorer** full UI — per-element confidence badges + overall reconstruction summary
- [x] Progressive reconstruction strategy — route simple vs complex images appropriately
- [x] Vector path editing controls in PropertiesPanel
- [~] Harder-image handling: crops of silhouettes, logos on photos, text on complex backgrounds (progressive router + confidence notes; deep-tuning deferred to backlog)

**Exit criteria:** logos and simple illustrations reconstruct as editable vectors, photos segment into editable regions with clear confidence labeling, and complex images degrade gracefully.

---

## Phase 4 — Sharing, Templates, Batch & PDF (v0.5)

Goal: distribution and productivity.

- [x] **Sharing** 🔬 — shareable links with view/edit access control 🔒; access revocation
- [x] **Templates** 🔬 — save any reconstructed design as a template; template gallery; start project from template
- [x] **Batch processing** 🔬 — upload multiple images, queue and track each reconstruction, open results
- [x] PDF export via **ExportService**
- [x] Refinement of editor UX, performance, and empty/error states

**Exit criteria:** a user shares an editable design via link, starts a project from the template gallery, batch-reconstructs several images at once, and exports to PDF.

---

## Post-MVP / Backlog

Ideas tracked for later, in priority order:

- [ ] Real-time live collaboration (CRDT-based multiplayer editing)
- [ ] Native mobile/desktop apps
- [ ] Advanced vector reconstruction of complex illustrations
- [ ] Deeper SAM 2 fine-tuning for design-graphic segmentation quality
- [ ] Font database expansion + better font matching
- [ ] Smart layer grouping (headers, hero sections, products, decorations)
- [ ] Background removal as a first-class tool
- [ ] Advanced image editing (crop, masks, filters) on segmented regions
- [ ] Plugin SDK / component system / design-system features (auto-layout)
- [ ] Marketplace, templates monetization

---

## Milestone map

| Milestone | Phase | Theme | Focus |
|-----------|-------|-------|-------|
| v0.1 | 1 | Foundations | Schema, upload, job queue |
| v0.2 | 1 | MVP editor | Reconstruction + Fabric editor |
| v0.3 | 2 | Persistence | Auth, projects, versioning |
| v0.4 | 3 | Fidelity | Vectorization, segmentation, confidence |
| v0.5 | 4 | Distribution | Sharing, templates, batch, PDF |

## Dependencies

- v0.1 is the release blocker for everything else (schema + pipeline + storage).
- v0.2 depends on v0.1 completion (renders the scene graph the pipeline produces).
- v0.3 depends on v0.2's project model (persists what the editor produces).
- v0.4 is logically independent of v0.3 but benefits from saved project fixtures during segmentation tuning.
- v0.5 depends on v0.3 (sharing and templates require auth) and on v0.2's editor.

## Risks & mitigations

- **OCR/font fidelity** — imperfect matching is acceptable only with the vector-outline fallback; keep confidence data from the start.
- **Segmentation quality** — SAM 2 is heavy; pin model size, run async, and always label output as approximate.
- **Editor scope creep** — Fabric.js covers v0.1–v0.5 needs; defer path/bone editing that Fabric doesn't handle well.
- **Pipeline cost/latency** — job queue + async workers keep uploads fast; batch phase amortizes model startup.
- **Schema churn** — SceneGraphSchema is the shared contract; version it (v1, v2...) before the `.p2l` format is user-facing.