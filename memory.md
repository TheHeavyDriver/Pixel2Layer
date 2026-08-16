# Project Memory — Pixel2Layer

Brief change log. Read first each session; append a short entry after every command.

## Log

| # | Date | Command | Files | Change |
|---|------|---------|-------|--------|
| 1 | 2025-08-16 | `create prd` | prd.md | Created full product PRD |
| 2 | 2025-08-16 | `create roadmap` | roadmap.md | Created phased roadmap v0.1-v0.5 |
| 3 | 2025-08-16 | `create the architecture` | architecture.md | Created system architecture doc |
| 4 | 2025-08-16 | `create rules` | AGENTS.md | Created rules file |
| 5 | 2025-08-16 | `revert` | AGENTS.md | Deleted after user rejection |
| 6 | 2025-08-16 | `create frontend design doc` | frontend-design.md | Created frontend UI/UX spec |
| 7 | 2025-08-16 | `create memory.md` | memory.md | Created this log |
| 8 | 2025-08-16 | `simplify memory format` | memory.md | Rewrote to brief log format |
| 9 | 2025-08-16 | `make logging automatic` | AGENTS.md | Created minimal hook to auto-update memory.md every command |
| 10 | 2026-08-16 | `implement v0.1` | package.json, docker-compose.yml, .gitignore | Scaffolded monorepo (workspaces), Postgres+Redis compose, .gitignore |
| 11 | 2026-08-16 | `implement v0.1` | packages/schema/* | SceneGraphSchema shared contract (TS types, v1) |
| 12 | 2026-08-16 | `implement v0.1` | apps/api/* | FastAPI app: config, storage backend, UploadService, JobQueue (memory/redis repos), upload/jobs/SSE routes |
| 13 | 2026-08-16 | `implement v0.1` | apps/api/tests | 16 pytest tests pass: upload validation, job lifecycle, SSE, API flow |
| 14 | 2026-08-16 | `implement v0.1` | apps/web/* | Next.js 16 + TS + Tailwind (v4 design tokens), upload modal + SSE progress screen, editor placeholder |
| 15 | 2026-08-16 | `verify` | apps/web | typecheck + build pass; end-to-end smoke test: upload→job→SSE→done verified live |
| 16 | 2026-08-16 | `commit` | — | Task #1 committed: `909fb1b feat(v0.1): scaffold monorepo...` |
| 17 | 2026-08-16 | `implement v0.2` | apps/api/{schemas,services} | SceneGraph pydantic models, ConfidenceScorer, ShapeDetector, ColorExtractor, TextDetector (vision-based, pluggable OCR), SceneGraphBuilder, pipeline orchestrator wired into JobQueue worker |
| 18 | 2026-08-16 | `implement v0.2` | apps/api/export_service.py | PNG/JPG/SVG export + .p2l save/load round-trip |
| 19 | 2026-08-16 | `implement v0.2` | apps/api/tests | 7 new test files → 37 pytest tests pass; ruff clean |
| 20 | 2026-08-16 | `verify` | apps/api | Live E2E: upload poster → pipeline → scene graph with shapes/colors/confidence |
| 21 | 2026-08-16 | `commit` | — | Task #2 committed: `52635fd feat(v0.2): reconstruction pipeline...` |
| 22 | 2026-08-16 | `implement v0.2` | apps/api/app/api/routes/export.py, apps/api/app/main.py, apps/api/tests/test_export_api.py | Export routes: POST /api/export (png/jpg/svg), /api/export/p2l (save), /api/export/import (load); 6 new tests → 43 pass; ruff clean |
| 23 | 2026-08-16 | `implement v0.2` | apps/web/package.json | Added fabric ^7.4.0; verified v7 group/ungroup + canvas APIs under jsdom |
| 24 | 2026-08-16 | `implement v0.2` | apps/web/src/lib/editor/{scene-fabric.ts,use-scene-history.ts} | Scene↔Fabric bridge (group flattening in canvasToScene, canvas-plane math) + snapshot undo/redo hook |
| 25 | 2026-08-16 | `implement v0.2` | apps/web/src/components/editor/{canvas-editor.tsx,layers-panel.tsx,properties-panel.tsx,editor-screen.tsx} | Fabric canvas editor w/ imperative handle, layers panel (rename/eye/lock/reorder), properties panel, editor screen + toolbar (undo/redo/group/align/zoom/export) |
| 26 | 2026-08-16 | `implement v0.2` | apps/web/src/app/editor/page.tsx, apps/web/src/lib/api.ts | Editor page now renders EditorScreen (jobId from searchParams); api.ts: getJob, exportScene, saveProjectP2l, importProjectP2l |
| 27 | 2026-08-16 | `verify` | apps/web apps/api | Web typecheck + build pass; fabric v7 APIs verified in jsdom; API 43 tests pass; ruff clean |
| 28 | 2026-08-16 | `commit` | — | Milestone committed: `237ec6e feat(v0.2): fabric editor, layers/properties panels, and export routes` |
| 29 | 2026-08-16 | `implement v0.2` | apps/web | Vitest + jsdom + @testing-library/react + vitest-canvas-mock; vitest.config.ts; 23 web tests (history hook, scene-fabric round-trip/group flatten, api client); `web:test` script; fix null-2D-context via canvas mock |
| 30 | 2026-08-16 | `commit` | — | `6994255 test(web): unit tests for scene-fabric bridge, history hook, and api client` |
| 31 | 2026-08-16 | `implement v0.2` | apps/web | Playwright e2e: config (API 8000 + web 3000), core-flow.spec (upload→editor→edit→export PNG/SVG→save/open .p2l); fixture poster.png |
| 32 | 2026-08-16 | `fix` | apps/web/src/lib/api.ts | SSE: resolve on terminal `update` event (done/failed), not just the trailing `done` event — Chromium emits ERR_INCOMPLETE_CHUNKED_ENCODING and drops it on fast jobs |
| 33 | 2026-08-16 | `verify` | apps/web apps/api | Playwright e2e passes (full exit-criteria flow); 23 vitest, 43 pytest, tsc, ruff all green; .gitignore playwright artifacts |
| 34 | 2026-08-16 | `commit` | — | `cecfae7 test(web): playwright e2e for core editor flow; fix SSE terminal event handling` — v0.2 checklist complete |
| 35 | 2026-08-16 | `implement v0.3` | apps/api | Self-hosted auth: JWT (pyjwt) + PBKDF2 hashing (`services/auth.py`); Store abstraction users/projects/versions with memory + asyncpg Postgres impls + DDL (`services/store.py`); `POST /api/auth/{register,login}`, `GET /me`; `POST/GET/PATCH/DELETE /api/projects` + versions save/list/restore, user-scoped; get_current_user dep; db_backend + jwt settings; compose Postgres → host port 5434 |
| 36 | 2026-08-16 | `implement v0.3` | apps/api/tests | +2 api routes, +auth service, +store → 16 new tests (auth + projects scoping/versions) → 59 pytest pass; ruff clean; live Postgres-backed E2E verified (register→CRUD→versions→restore→cross-user 404) |
| 37 | 2026-08-16 | `implement v0.3` | apps/web | Auth client (register/login/logout/me, getToken/setToken, Bearer authFetch) + project/version API fns in `lib/api.ts`; /login + /signup pages; /dashboard (list/open/rename/delete, logout); editor loads `?project=`, CloudSaveControl (save/update project, versions menu, restore); home nav shows Sign in / My projects / Log out |
| 38 | 2026-08-16 | `verify` | apps/web | 11 new vitest auth/project api tests (localStorage shim setup for jsdom) → 34 pass; tsc + build green; Playwright auth-flow e2e (signup→save project→version restore→dashboard reopen→logout) + core-flow pass (2/2); API e2e runs with DB_BACKEND=memory for hermeticity |
| 39 | 2026-08-16 | `commit` | — | Milestone committed: `027724f feat(v0.3): auth, project persistence, and version history` — v0.3 auth & persistence complete (email/password JWT, project CRUD, version history, dashboard) |
| 40 | 2026-08-16 | `implement v0.4` | apps/api/services/{vectorizer,segmenter,progressive}.py, app/api/routes/storage.py | Vectorizer (OpenCV contour→SVG path), pluggable Segmenter (default VisionSegmenter foreground separation → masked PNG cutouts served via /api/storage/{key}), ProgressiveRouter (graphic vs photographic routing) |
| 41 | 2026-08-16 | `implement v0.4` | apps/api/{services/{pipeline,scene_graph_builder,export_service,pipeline_worker}.py, schemas/scene_graph.py, app/main.py} | Pipeline wires vectorizing+segmenting stages & complexity metadata; SceneGraph adds `complexity`; builder emits vector/image elements; export renders vector paths (SVG path + raster flattened); storage router registered |
| 42 | 2026-08-16 | `implement v0.4` | apps/api/tests/{test_vectorizer_segmenter,test_progressive,test_pipeline_v04,test_export_service}.py | +19 tests (vectorizer, segmenter, progressive routing, pipeline stages/cutouts, vector export) → 71 pytest pass; ruff clean; live E2E verified both routing branches (photo→segment+cutout, graphic→vector) |
| 43 | 2026-08-16 | `implement v0.4` | apps/web/src/components/editor/{properties-panel,editor-screen}.tsx, apps/web/src/lib/editor/{scene-fabric.ts,scene-fabric.test.ts}, packages/schema/src/index.ts | Web: vector path editing + confidence summary UI (complexity, per-category, per-element badges, notes); scene-fabric resolves /api refs via API_BASE; 36 vitest pass, tsc clean |
| 44 | 2026-08-16 | `fix` | apps/web/src/components/progress-screen.tsx | Move data-testid="overall-progress" to track container (0-width inner bar was hidden; flaky e2e) |
| 45 | 2026-08-16 | `verify` | apps/web | 2 Playwright e2e pass consistently (auth + core flow); next build green |
| 46 | 2026-08-16 | `commit` | — | v0.4 milestone: vectorizer, segmentation, confidence UI, progressive routing |
| 47 | 2026-08-16 | `implement v0.5` | apps/api/{services/store.py, api/routes/{sharing,templates,batches}.py}, app/main.py, services/{job_queue,export_service}.py, routes/export.py | Backend: share/template/batch persistence (Store + Postgres DDL + memory), share routes (create/list/revoke + public view/edit), template routes (save/gallery/get/delete), batch routes (create + status), PDF export via Pillow |
| 48 | 2026-08-16 | `implement v0.5` | apps/api/tests/{test_sharing,test_templates,test_batches}.py, test_export_api.py, test_export_service.py | 15 new tests (sharing scoping/revoke, template gallery/ownership, batch job tracking, PDF) → 86 pytest pass; ruff clean |
| 49 | 2026-08-16 | `implement v0.5` | apps/web/src/lib/api.ts, api client tests (v05-api.test.ts) | Web api client: createShare/listShares/revokeShare/shareUrl/getSharedProject/updateSharedProject, createTemplate/listTemplates/getTemplate/deleteTemplate, createBatch/getBatch, pdf export format; 9 new vitest → 45 pass |
| 50 | 2026-08-16 | `implement v0.5` | apps/web/src/app/editor/page.tsx, share/[token]/page.tsx, templates/page.tsx, page.tsx, components/editor/editor-screen.tsx | Editor: shareToken+templateId load paths, ShareControl dialog (view/edit, copy, revoke), Save-as-template, PDF export, view-only mode; /share/[token] page; /templates gallery; home multi-file/batch upload + Templates link; UploadModal multi-file; BatchProgressScreen |
| 51 | 2026-08-16 | `implement v0.5` | apps/web/e2e/v05-flow.spec.ts | Playwright e2e: sharing create→open→revoke, template save→gallery→reuse + PDF export; home "Get started"→"Upload an image" button update in existing specs |
| 52 | 2026-08-16 | `verify` | apps/api apps/web | 86 pytest + 45 vitest + 4 Playwright e2e pass; tsc + next build green; ruff clean — v0.5 exit criteria met (share/edit/revoke, template gallery start, batch, PDF) |
| 53 | 2026-08-16 | `commit` | — | v0.5 milestone: sharing, templates, batch processing, PDF export |

## Files

- `README.md` — stub (unchanged)
- `description.md` — original spec (unchanged)
- `prd.md`, `roadmap.md`, `architecture.md`, `frontend-design.md` — created
- `memory.md` — this log
- `package.json`, `docker-compose.yml`, `.gitignore` — monorepo root
- `packages/schema/` — SceneGraphSchema shared contract (TS)
- `apps/api/` — FastAPI backend (upload, job queue, SSE, v0.2 reconstruction pipeline); `.venv` + `uv`
- `apps/web/` — Next.js 16 frontend (upload modal, SSE progress screen, Fabric.js editor: canvas-editor/layers-panel/properties-panel/editor-screen)

## Convention

Read this each session. After every command, append one brief row: command, files touched, change. Append only; never rewrite history.