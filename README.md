# Saint & Scholar

Ancient wisdom + modern science, delivered as a dual-retrieval RAG API.

Saint & Scholar answers science questions in the literary voice of selected spiritual/philosophical figures by retrieving:
- factual grounding from `data/knowledge`
- stylistic grounding from `data/style`

The API returns an answer with citations and request metadata.

## Current status (2026-03-05)

- FastAPI backend with endpoints: `/`, `/health`, `/v1/figures`, `/v1/ask`, `/v1/admin/reindex`
- Static no-build frontend under `src/saint_scholar/api/static/`
- Frontend uses in-app overlays for site actions, including a styled "New Discourse" confirmation modal
- Response citations render collapsed by default and can be expanded per answer
- Local vector-store pipeline with manifest-based change detection
- Optional automatic PubMed bootstrap when `data/knowledge` is empty
- Rate limiting for `/v1/ask` (in-memory, per-process, per-client IP)
- Test suite in `tests/` for API and core retrieval/ingest/generation helpers

## Project layout

- `src/saint_scholar/api/main.py`: app lifecycle, validation, CORS, security headers, rate limiting, routes
- `src/saint_scholar/ingest.py`: corpus loading/chunking, embedding generation, vector persistence
- `src/saint_scholar/retrieval.py`: retrieval and resource rebuild loading
- `src/saint_scholar/generation.py`: Anthropic prompt assembly + completion call
- `src/saint_scholar/populate_knowledge.py`: PubMed corpus bootstrap utility
- `scripts/smoke_api.py`: end-to-end smoke test against a running API
- `ops/`: deployment helpers (`deploy.sh`, `rollback.sh`, nginx, systemd)

## Requirements

- Python `>=3.11`
- Anthropic API key (`ANTHROPIC_API_KEY`)
- Internet access at least once for:
  - downloading the sentence-transformers embedding model cache
  - PubMed fetch/bootstrap operations (if used)

## Quick start

1. Create and activate venv.

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install runtime dependencies and package.

```bash
pip install -r requirements.txt
pip install -e .
```

3. Configure environment variables.

```bash
copy .env.example .env
```

Required:

```bash
ANTHROPIC_API_KEY=your_key_here
ADMIN_API_KEY=set_a_long_random_admin_token_here
```

Common optional settings:

```bash
NCBI_EMAIL=you@example.com
SAINT_SCHOLAR_AUTO_POPULATE_KNOWLEDGE=1
VECTOR_STORE_PATH=./vector_store
CORS_ALLOWED_ORIGINS=http://127.0.0.1:8000
RATE_LIMIT_MAX_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=60
```

4. Ensure corpus files exist.
- Style corpus: `data/style/<figure>/...` (required for figures you query)
- Knowledge corpus: `data/knowledge/...` (or let auto-bootstrap populate it)

5. Build/refresh vector store.

```bash
python -m saint_scholar.ingest
```

6. Run API.

```bash
uvicorn saint_scholar.api.main:app --host 127.0.0.1 --port 8000
```

Open: `http://127.0.0.1:8000/`

## API endpoints

- `GET /health`: service health + key/vector-store checks (`ok` or `degraded`)
- `GET /v1/figures`: configured figures plus discovered `data/style/*` folders
- `POST /v1/ask`: retrieval + generation response with citations and metadata
- `POST /v1/admin/reindex`: force rebuild (requires `x-admin-token` matching `ADMIN_API_KEY`)
- `GET /`: static frontend shell with figure selection, chat UI, expandable citations, and a custom new-discourse confirmation flow

Ask example:

```bash
curl -X POST "http://127.0.0.1:8000/v1/ask" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"How does meditation physically change the brain?\",\"figure\":\"buddha\"}"
```

Admin reindex:

```bash
curl -X POST "http://127.0.0.1:8000/v1/admin/reindex" ^
  -H "x-admin-token: YOUR_ADMIN_API_KEY"
```

## Testing

```bash
pip install pytest
python -m pytest -q
python scripts/smoke_api.py --base-url http://127.0.0.1:8000
```

## Verification

Run the core repo hygiene and Python test suite with:
```bash
npm run verify
```

This runs:
- Ruff lint
- Ruff format check
- ESLint
- Python tests

Run the Playwright UI suite with:
```bash
npm run verify:ui
```

## Corpus tooling

- `python -m saint_scholar.populate_knowledge`
- `python scripts/fetch_pubmed.py --query "..." --domain neuroscience --retmax 10`
- `python scripts/expand_corpus.py`
- `python scripts/fetch_style_texts.py --figure buddha` (or `--all`)
- `python scripts/convert_txt_to_md.py --data-root data`

## Operational notes

- Paths are relative to repo root (`data`, `vector_store`), so run commands from this directory.
- `data/knowledge`, `data/style`, `.env`, and `vector_store` are local artifacts (gitignored).
- `/v1/ask` returns `503` if retrieval yields no knowledge or no style chunks.
