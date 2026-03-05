# Saint & Scholar — Local Quickstart

## Prerequisites

- Python 3.11+
- An Anthropic API key

## 1. Clone & set up the virtual environment

```bash
git clone <repo-url> saint-scholar
cd saint-scholar
python -m venv .venv
```

Activate the venv:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows (Git Bash / MSYS2)
source .venv/Scripts/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

## 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```
ANTHROPIC_API_KEY=sk-ant-...
ADMIN_API_KEY=some-random-secret
```

## 3. Populate the knowledge corpus

This fetches PubMed abstracts across all domains (neuroscience, psychology, genetics, nutrition, immunology, etc.). Takes a few minutes due to API rate limits.

```bash
python src/saint_scholar/populate_knowledge.py --per-query 12
```

You should see output like:

```
Knowledge population complete. Wrote ~370 article(s) into data/knowledge.
```

Verify domain folders exist:

```bash
ls data/knowledge/
# Expected: consciousness/ ecology/ exercise_science/ genetics/ immunology/
#           longevity/ neuroscience/ nutrition/ psychology/ social_science/
```

## 4. Build the vector store

This embeds all knowledge and style texts into the local vector index. First run downloads the embedding model (~80 MB).

```bash
python src/saint_scholar/ingest.py
```

You should see a summary like:

```
Knowledge: ~457 chunks across 10 domains
Style: ~4547 chunks across 10 figures
Stored in ./vector_store
```

## 5. Run the API server

```bash
uvicorn saint_scholar.api.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 in your browser.

## 6. Smoke test (optional)

In a separate terminal (with the venv activated):

```bash
python scripts/smoke_api.py
```

This hits `/health`, `/v1/figures`, and `/v1/ask` and reports pass/fail for each.

## What to verify

- **No auto-scroll drift** — page should not scroll on its own when it loads or after the 30-second health check fires
- **Send a message** — pick a figure, type a question, confirm smooth scroll to the new message and that citations appear
- **Mobile** — resize browser to 375px or 414px width:
  - Character bar should show avatar-only pills with horizontal swipe
  - Input area should feel full-width, send button should be easy to tap
  - Prompt chips should be at least 44px tall
- **Info panel** — click the (i) button in the header, verify the drawer slides in from the right. Close via X button, clicking the overlay, or pressing Escape
- **Knowledge domains** — ask a question about nutrition, immunity, or exercise and verify relevant citations appear from those domains

## Important notes

- `data/knowledge/`, `data/style/`, and `vector_store/` are all in `.gitignore` — they are generated locally and not committed
- If you change knowledge queries in `populate_knowledge.py`, you need to re-run steps 3 and 4
- The `.env` file is also gitignored — never commit API keys
