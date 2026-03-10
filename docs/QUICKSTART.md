# Saint & Scholar - Local Quickstart

## Prerequisites

- Python `>=3.11`
- Anthropic API key
- Run all commands from repo root

## 1. Create and activate venv

```bash
python -m venv .venv
```

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

Optional test dependency:

```bash
pip install pytest
```

## 2. Configure `.env`

```bash
# Linux/macOS
cp .env.example .env

# Windows PowerShell
copy .env.example .env
```

Required:

```bash
ANTHROPIC_API_KEY=sk-ant-...
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

## 3. Prepare corpus data

Style corpus is required:
- `data/style/<figure>/...` containing `.md` or `.txt` texts

Knowledge corpus options:
- Manual bootstrap:

```bash
python -m saint_scholar.populate_knowledge --per-query 12
```

- Auto-bootstrap on ingestion when `data/knowledge` is empty:
  set `SAINT_SCHOLAR_AUTO_POPULATE_KNOWLEDGE=1` (default behavior unless set to `0`)

## 4. Build vector store

```bash
python -m saint_scholar.ingest
```

Output is written to `./vector_store` (or `VECTOR_STORE_PATH`).

## 5. Run API

```bash
uvicorn saint_scholar.api.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

## 6. Validate

Smoke test against running API:

```bash
python scripts/smoke_api.py --base-url http://127.0.0.1:8000
```

Run tests:

```bash
python -m pytest -q
```

## API behavior notes

- `/health` is `ok` only when vector store exists and `ANTHROPIC_API_KEY` is set.
- `/v1/figures` returns configured figures plus any `data/style/*` folder names.
- `/v1/ask` is IP rate-limited and returns `503` if no knowledge/style chunks are retrieved.
- `/v1/admin/reindex` requires `x-admin-token` and `ADMIN_API_KEY` length >= 16.

## Troubleshooting

- `ModuleNotFoundError` (for `fastapi`, `numpy`, etc.): activate venv and reinstall dependencies.
- Embedding cache error in ingest: run once with internet access to download `all-MiniLM-L6-v2`.
- `/v1/ask` model/auth errors: verify `ANTHROPIC_API_KEY`.
