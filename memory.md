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

## Files

- `README.md` — stub (unchanged)
- `description.md` — original spec (unchanged)
- `prd.md`, `roadmap.md`, `architecture.md`, `frontend-design.md` — created
- `memory.md` — this log
- `package.json`, `docker-compose.yml`, `.gitignore` — monorepo root
- `packages/schema/` — SceneGraphSchema shared contract (TS)
- `apps/api/` — FastAPI backend (upload, job queue, SSE); `.venv` + `uv`
- `apps/web/` — Next.js 16 frontend (upload modal, SSE progress screen)

## Convention

Read this each session. After every command, append one brief row: command, files touched, change. Append only; never rewrite history.