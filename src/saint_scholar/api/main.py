from __future__ import annotations

import hmac
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from saint_scholar.config import FIGURES

# Configure structured JSON logging when the optional formatter is installed.
LOG_FORMAT = os.getenv("LOG_FORMAT", "json").lower()  # json or text

if LOG_FORMAT == "json":
    try:
        from pythonjsonlogger import jsonlogger
    except ModuleNotFoundError:
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        logger = logging.getLogger("saint_scholar")
        logger.warning("python-json-logger is not installed; falling back to text logs.")
    else:
        log_handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(client_ip)s",
            timestamp=True,
        )
        log_handler.setFormatter(formatter)
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            handlers=[log_handler],
        )
else:
    # Fallback to text logging
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

logger = logging.getLogger("saint_scholar")

DATA_STYLE_DIR = Path("data") / "style"


def _humanize_slug(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").title()


def _available_figures() -> dict[str, dict[str, Any]]:
    figures: dict[str, dict[str, Any]] = {k: dict(v) for k, v in FIGURES.items()}
    if not DATA_STYLE_DIR.exists():
        return figures

    for folder in sorted(DATA_STYLE_DIR.iterdir()):
        if not folder.is_dir():
            continue
        key = folder.name.strip()
        if not key or key in figures:
            continue
        figures[key] = {
            "name": _humanize_slug(key),
            "tradition": "Unknown",
            "tagline": "Imported style corpus",
            "icon": "Section",
            "color": "#6B7280",
        }
    return figures


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    figure: str = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        # Strip control characters (keep newlines/tabs for formatting)
        import unicodedata

        cleaned = "".join(
            c for c in value if not unicodedata.category(c).startswith("C") or c in "\n\r\t"
        )
        normalized = cleaned.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized

    @field_validator("figure")
    @classmethod
    def validate_figure(cls, value: str) -> str:
        normalized = value.strip().lower()
        available_figures = _available_figures()
        if normalized not in available_figures:
            available = ", ".join(sorted(available_figures.keys()))
            raise ValueError(f"unknown figure '{normalized}'. Available: {available}")
        return normalized


class Citation(BaseModel):
    id: str
    type: str
    score: float
    title: str | None = None
    year: str | None = None
    journal: str | None = None
    pmid: str | None = None
    url: str | None = None
    authors: str | None = None
    abstract_preview: str | None = None
    work: str | None = None
    figure: str | None = None
    tradition: str | None = None


class AskMeta(BaseModel):
    request_id: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    figure: str
    knowledge_count: int
    style_count: int
    generated_at: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    meta: AskMeta


class ReindexResponse(BaseModel):
    status: str
    request_id: str
    rebuilt_at: str
    knowledge_total: int
    style_total: int


def _knowledge_citation(chunk: dict[str, Any]) -> Citation:
    metadata = chunk.get("metadata", {})
    pmid = str(metadata.get("pmid", "")).strip()
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None

    # Format authors string from list
    raw_authors = metadata.get("authors", "")
    if isinstance(raw_authors, list):
        authors = ", ".join(raw_authors[:3])
        if len(raw_authors) > 3:
            authors += " et al."
    else:
        authors = str(raw_authors).strip() or None

    # Abstract preview from chunk text
    text = str(chunk.get("text", "")).strip()
    abstract_preview = (text[:150] + "...") if len(text) > 150 else text or None

    return Citation(
        id=str(chunk.get("id", "")),
        type="knowledge",
        score=float(chunk.get("score", 0.0)),
        title=str(metadata.get("title", "")) or None,
        year=str(metadata.get("year", "")) or None,
        journal=str(metadata.get("journal", "")) or None,
        pmid=pmid or None,
        url=url,
        authors=authors or None,
        abstract_preview=abstract_preview,
    )


def _style_citation(chunk: dict[str, Any]) -> Citation:
    metadata = chunk.get("metadata", {})

    # Excerpt preview from chunk text
    text = str(chunk.get("text", "")).strip()
    # Take the first line of the passage as preview
    first_line = text.split("\n")[0].strip().lstrip("# ")
    abstract_preview = (first_line[:150] + "...") if len(first_line) > 150 else first_line or None

    return Citation(
        id=str(chunk.get("id", "")),
        type="style",
        score=float(chunk.get("score", 0.0)),
        work=str(metadata.get("work", "")) or None,
        figure=str(metadata.get("figure", "")) or None,
        tradition=str(metadata.get("tradition", "")) or None,
        url=str(metadata.get("citation_url", "")) or None,
        abstract_preview=abstract_preview,
    )


def _build_citations(retrieval: dict[str, Any]) -> list[Citation]:
    citations: list[Citation] = []
    for chunk in retrieval.get("knowledge_chunks", []):
        citations.append(_knowledge_citation(chunk))
    for chunk in retrieval.get("style_chunks", []):
        citations.append(_style_citation(chunk))
    return citations


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY is not set - /v1/ask will fail at runtime.")
    yield
    # Shutdown
    logger.info("Saint & Scholar API shutting down.")


app = FastAPI(title="Saint & Scholar API", version="0.1.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ---------------------------------------------------------------------------
# Custom exception handler to include request ID in errors
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Include request_id in error responses for traceability."""
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": request_id,
        },
        headers=exc.headers,
    )


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Generate unique request ID for traceability."""
    request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Rate limiter — persistent SQLite-backed token-bucket per IP for /v1/ask
# ---------------------------------------------------------------------------
_RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
_RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
_RATE_LIMIT_DB = Path(os.getenv("RATE_LIMIT_DB_PATH", ".rate_limit.db"))


class PersistentRateLimiter:
    """SQLite-backed rate limiter that persists across restarts."""

    def __init__(self, db_path: Path, max_requests: int, window_seconds: int):
        self.db_path = db_path
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    client_ip TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (client_ip, timestamp)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON rate_limits(timestamp)
            """)
            conn.commit()

    def check_rate_limit(self, client_ip: str) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        now = time.time()
        cutoff = now - self.window_seconds

        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                # Clean up expired entries
                conn.execute("DELETE FROM rate_limits WHERE timestamp < ?", (cutoff,))

                # Count recent requests from this IP
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM rate_limits WHERE client_ip = ? AND timestamp >= ?",
                    (client_ip, cutoff),
                )
                count = cursor.fetchone()[0]

                if count >= self.max_requests:
                    return False

                # Record this request
                conn.execute(
                    "INSERT INTO rate_limits (client_ip, timestamp) VALUES (?, ?)",
                    (client_ip, now),
                )
                conn.commit()
                return True
        except sqlite3.Error as exc:
            logger.error(
                "Rate limiter database error: %s",
                exc,
                extra={"client_ip": client_ip, "error_type": "rate_limiter_db"},
            )
            # Fail open to avoid blocking legitimate users on DB issues
            return True


_rate_limiter = PersistentRateLimiter(_RATE_LIMIT_DB, _RATE_LIMIT_MAX, _RATE_LIMIT_WINDOW)


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    return _rate_limiter.check_rate_limit(client_ip)


# ---------------------------------------------------------------------------
# Request logging
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    request_id = getattr(request.state, "request_id", "unknown")
    client_ip = request.client.host if request.client else "unknown"

    # Structured logging with context
    logger.info(
        "%s %s %s %dms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        extra={
            "request_id": request_id,
            "client_ip": client_ip,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
        },
    )
    return response


@app.get("/health")
def health() -> dict[str, Any]:
    from saint_scholar.config import VECTOR_STORE_DIR

    vector_store_ready = Path(VECTOR_STORE_DIR).exists() and any(
        Path(VECTOR_STORE_DIR).glob("*.npy")
    )
    api_key_set = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    return {
        "status": "ok" if (vector_store_ready and api_key_set) else "degraded",
        "service": "saint-scholar-api",
        "time": datetime.now(tz=timezone.utc).isoformat(),
        "checks": {
            "vector_store": "ready" if vector_store_ready else "missing",
            "anthropic_key": "set" if api_key_set else "missing",
        },
    }


@app.get("/v1/figures")
def figures() -> dict[str, Any]:
    return {"figures": _available_figures()}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/v1/ask", response_model=AskResponse)
def ask(payload: AskRequest, request: Request) -> AskResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before trying again.",
        )

    started = time.perf_counter()
    request_id = getattr(request.state, "request_id", str(uuid4()))

    # Import lazily so non-RAG endpoints (like /health) can start without loading heavy deps.
    from saint_scholar.generation import generate_response
    from saint_scholar.retrieval import dual_retrieve

    retrieval = dual_retrieve(question=payload.question, figure=payload.figure)
    knowledge_chunks = retrieval.get("knowledge_chunks", [])
    style_chunks = retrieval.get("style_chunks", [])

    if not knowledge_chunks:
        raise HTTPException(status_code=503, detail="No knowledge passages were retrieved.")
    if not style_chunks:
        raise HTTPException(
            status_code=503,
            detail=f"No style passages were retrieved for figure '{payload.figure}'.",
        )

    try:
        generation = generate_response(
            question=payload.question,
            figure=payload.figure,
            knowledge_chunks=knowledge_chunks,
            style_chunks=style_chunks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Generation failed",
            extra={"request_id": request_id, "client_ip": client_ip},
        )
        raise HTTPException(status_code=500, detail="Internal server error.") from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    citations = _build_citations(retrieval)

    return AskResponse(
        answer=str(generation.get("response", "")),
        citations=citations,
        meta=AskMeta(
            request_id=request_id,
            model=str(generation.get("model", "")),
            input_tokens=int(generation.get("input_tokens", 0)),
            output_tokens=int(generation.get("output_tokens", 0)),
            latency_ms=latency_ms,
            figure=payload.figure,
            knowledge_count=len(knowledge_chunks),
            style_count=len(style_chunks),
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        ),
    )


@app.post("/v1/admin/reindex", response_model=ReindexResponse)
def admin_reindex(
    request: Request, x_admin_token: str | None = Header(default=None)
) -> ReindexResponse:
    admin_token = os.getenv("ADMIN_API_KEY", "").strip()
    request_id = getattr(request.state, "request_id", str(uuid4()))
    client_ip = request.client.host if request.client else "unknown"
    if not admin_token or len(admin_token) < 16:
        logger.warning(
            "Admin reindex attempted while disabled",
            extra={"request_id": request_id, "client_ip": client_ip},
        )
        raise HTTPException(
            status_code=503,
            detail="Admin reindex is disabled. Set ADMIN_API_KEY (min 16 chars) to enable.",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        logger.warning(
            "Admin reindex unauthorized",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "token_prefix": (x_admin_token or "")[:8],
            },
        )
        raise HTTPException(status_code=401, detail="Unauthorized.")

    from saint_scholar.retrieval import rebuild_resources

    started = time.perf_counter()
    logger.info(
        "Admin reindex started",
        extra={
            "request_id": request_id,
            "client_ip": client_ip,
            "token_prefix": x_admin_token[:8],
        },
    )
    try:
        resources = rebuild_resources(force_rebuild=True)
    except Exception:
        logger.exception(
            "Admin reindex failed",
            extra={"request_id": request_id, "client_ip": client_ip},
        )
        raise

    stats = resources.get("stats", {})
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "Admin reindex completed",
        extra={
            "request_id": request_id,
            "client_ip": client_ip,
            "latency_ms": elapsed_ms,
            "knowledge_total": int(stats.get("knowledge_total", 0)),
            "style_total": int(stats.get("style_total", 0)),
        },
    )

    return ReindexResponse(
        status="ok",
        request_id=request_id,
        rebuilt_at=datetime.now(tz=timezone.utc).isoformat(),
        knowledge_total=int(stats.get("knowledge_total", 0)),
        style_total=int(stats.get("style_total", 0)),
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
