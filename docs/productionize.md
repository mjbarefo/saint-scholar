# Saint & Scholar Productionization Notes

Last updated: 2026-03-04

## Current state (implemented)

- Runtime: `FastAPI` API plus static frontend served from `src/saint_scholar/api/static/`.
- Retrieval: dual index (`knowledge` + `style`) with local embeddings in `vector_store/`.
- Endpoints:
  - `GET /health`
  - `GET /v1/figures`
  - `POST /v1/ask`
  - `POST /v1/admin/reindex` (header `x-admin-token`, backed by `ADMIN_API_KEY`)
  - `GET /` (web UI)
- Ingestion:
  - Loads `.md`/`.txt` corpora under `data/knowledge` and `data/style`.
  - Uses sidecar `.metadata.json` files for provenance.
  - Persists normalized embeddings as `.npy` + metadata JSON files.
  - Skips rebuild when corpus manifest is unchanged.

## What is already production-leaning

- API request/response schemas are explicit with Pydantic models.
- `/v1/ask` returns citation payloads and generation metadata.
- Admin reindex path is protected by constant-time token comparison.
- Smoke test script exists: `scripts/smoke_api.py`.

## Gaps to close before public launch

1. Security hardening
- Add rate limiting on `/v1/ask` and `/v1/admin/reindex`.
- Add CORS allowlist (currently not explicitly configured).
- Add stricter error redaction so provider/internal exceptions are not fully exposed.

2. Operational readiness
- Add structured JSON logging (request id, latency, figure, retrieval counts).
- Add containerization (`Dockerfile` + `docker-compose.yml`).
- Add startup and health probes suitable for orchestration.

3. Persistence and analytics
- Add optional request log store (Postgres) with redaction policy.
- Track model cost and retrieval quality metrics over time.

4. CI/CD and verification
- Add lint/type/test workflow in GitHub Actions.
- Add deploy workflow (droplet SSH or registry-based).
- Add synthetic post-deploy smoke checks (`/health`, `/v1/ask`).

## Suggested deployment shape (single droplet first)

- Reverse proxy: Caddy or Nginx with TLS.
- App: one `uvicorn` process manager setup (systemd or container).
- Optional worker process only if reindexing is moved off request path.
- Storage:
  - Keep `data/` and `vector_store/` on persistent disk volume.
  - Snapshot/backup these paths regularly.

## Practical next implementation order

1. Add Docker support for current API + static frontend.
2. Add rate limiting and CORS policy.
3. Add structured logging + request id propagation.
4. Add CI pipeline (lint/test/smoke).
5. Add deployment script and backup routine.

## Definition of done for Production v1

- HTTPS deployment with automated restarts.
- Protected admin reindex and rate-limited ask endpoint.
- Observable logs and basic alerting on error rate/latency.
- Repeatable deployment and smoke-test verification.
