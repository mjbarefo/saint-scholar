# Saint & Scholar

Ancient wisdom. Modern science. Dual-retrieval RAG API.

Saint & Scholar answers modern science questions in the literary style of historical spiritual and philosophical figures. It retrieves:
- factual grounding from a knowledge corpus (`data/knowledge`), and
- voice/style grounding from a style corpus (`data/style`).

Then it generates one response with citations and metadata.

## What is in this repo

- `src/saint_scholar/api/main.py`: FastAPI app (`/health`, `/v1/figures`, `/v1/ask`, `/v1/admin/reindex`, `/`)
- `src/saint_scholar/ingest.py`: corpus loading, chunking, embedding, vector persistence
- `src/saint_scholar/retrieval.py`: dual retrieval (knowledge + style)
- `src/saint_scholar/generation.py`: prompt assembly + Anthropic generation
- `src/saint_scholar/populate_knowledge.py`: PubMed bootstrap utility
- `src/saint_scholar/api/static/`: no-build frontend (`index.html`, `app.js`, `styles.css`)
- `scripts/`: corpus helpers + API smoke test
- `data/`: local knowledge/style corpus files (markdown + metadata sidecars)
- `vector_store/`: local persisted embeddings and metadata

## Runtime architecture

```text
Question + Figure
  -> Knowledge Retrieval (top_k=5)
  -> Style Retrieval (top_k=3, figure-filtered)
  -> Prompt Assembly (K passages + S passages)
  -> Anthropic Claude
  -> Answer + citations + usage metadata
```

## Requirements

- Python 3.11+
- Anthropic API key
- First run with internet access to fetch embedding model cache if not already present

## Quickstart

1. Create a virtual environment and install dependencies.
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

2. Create `.env` from `.env.example` and set:
```bash
ANTHROPIC_API_KEY=your_key_here
ADMIN_API_KEY=your_long_random_admin_token
# Optional: NCBI email used by PubMed E-utilities calls
NCBI_EMAIL=you@example.com
```

3. Build or refresh the local vector store:
```bash
python -m saint_scholar.ingest
```

Notes:
- If `data/knowledge` is empty, ingestion attempts an automatic PubMed bootstrap.
- Set `SAINT_SCHOLAR_AUTO_POPULATE_KNOWLEDGE=0` to disable auto-bootstrap.

4. Start the API:
```bash
uvicorn saint_scholar.api.main:app --host 0.0.0.0 --port 8000
```

5. Open the app:
```text
http://127.0.0.1:8000/
```

## API endpoints

- `GET /health`: liveness + service metadata
- `GET /v1/figures`: available figure map (config + discovered folders in `data/style`)
- `POST /v1/ask`: retrieve + generate response
- `POST /v1/admin/reindex`: force rebuild vector store (requires `x-admin-token`)
- `GET /`: static web UI

Ask example:
```bash
curl -X POST "http://127.0.0.1:8000/v1/ask" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"How does meditation physically change the brain?\",\"figure\":\"buddha\"}"
```

Reindex example:
```bash
curl -X POST "http://127.0.0.1:8000/v1/admin/reindex" \
  -H "x-admin-token: ${ADMIN_API_KEY}"
```

Smoke test example:
```bash
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

- `python -m saint_scholar.populate_knowledge`: curated PubMed corpus bootstrap
- `python scripts/fetch_pubmed.py --query "..." --domain neuroscience --retmax 10`
- `python scripts/expand_corpus.py`: run a batch of curated PubMed queries
- `python scripts/fetch_style_texts.py --figure buddha` (or `--all`)
- `python scripts/convert_txt_to_md.py --data-root data`

## Configuration

Central constants live in `src/saint_scholar/config.py`:
- embedding model (`all-MiniLM-L6-v2`)
- chunk sizes
- retrieval top-k values
- generation model and token limit
- curated figure display metadata

## Repo hygiene

Generated artifacts are intentionally ignored:
- `.venv/`, `__pycache__/`, `*.egg-info/`
- `vector_store/`, `.bak/`, and legacy `chroma_store/` (if present)

## Data attribution

- Scientific sources: PubMed metadata/abstracts where available
- Style sources: public-domain spiritual/philosophical texts
- References:
  - https://pubmed.ncbi.nlm.nih.gov/
  - https://www.gutenberg.org/
  - https://www.accesstoinsight.org/
