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
| 34 | 2026-08-16 | `commit` | — | v0.2 e2e + SSE fix committed |

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