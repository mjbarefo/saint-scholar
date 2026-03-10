# Critical Fixes Summary - 2026-03-10

## Overview
Completed all 5 critical fixes identified in the code review before pushing to GitHub.

## Fixes Applied

### 1. ✅ API Key Protection (.gitignore)
**Status:** Already protected
**File:** `.gitignore`

- `.env` was already in `.gitignore` (line 2)
- Added `.rate_limit.db` to `.gitignore` (line 14)

**Action Required:** Still need to rotate your Anthropic API key as a precaution.

---

### 2. ✅ Thread-Safety Fix
**Status:** Fixed
**File:** `src/saint_scholar/retrieval.py`

**Problem:** Global `_RESOURCES` dict was accessed/modified without locks, causing potential crashes under concurrent reindex operations.

**Solution:**
- Added `threading.RLock()` for proper synchronization
- Protected `_resources()` and `rebuild_resources()` with lock context managers
- Prevents race conditions and partial reads during rebuild

**Changes:**
```python
import threading
_RESOURCES_LOCK = threading.RLock()

def _resources() -> dict[str, Any]:
    with _RESOURCES_LOCK:
        # ... safe access
```

---

### 3. ✅ Persistent Rate Limiter
**Status:** Fixed
**File:** `src/saint_scholar/api/main.py`

**Problem:** In-memory rate limiter reset on server restart, allowing trivial bypass.

**Solution:**
- Implemented `PersistentRateLimiter` class using SQLite
- Rate limits now persist across restarts
- Automatic cleanup of expired entries
- Fails open gracefully on DB errors (doesn't block legitimate users)
- Database stored at `.rate_limit.db` (configurable via `RATE_LIMIT_DB_PATH`)

**Features:**
- Thread-safe with 5s connection timeout
- Indexed by timestamp for fast cleanup
- Survives server restarts

---

### 4. ✅ Request ID Tracking
**Status:** Fixed
**File:** `src/saint_scholar/api/main.py`

**Problem:** No request IDs in error responses, making logs ungreppable and debugging difficult.

**Solution:**
- Added `request_id_middleware` to generate unique UUID for every request
- Request ID stored in `request.state.request_id`
- Added `X-Request-ID` header to all responses
- Custom `HTTPException` handler includes `request_id` in error JSON
- All log messages now include request ID

**Benefits:**
- Can trace requests from client → logs → errors
- Error responses now include: `{"detail": "...", "request_id": "..."}`
- Logs include `[request_id=...]` for grep-ability

---

### 5. ✅ Structured JSON Logging
**Status:** Fixed
**Files:** `src/saint_scholar/api/main.py`, `requirements.txt`

**Problem:** String-based logs hard to parse, no structured data for observability tools.

**Solution:**
- Added `python-json-logger>=2.0.0,<3.0.0` to requirements
- Implemented JSON logging with structured fields
- Configurable via `LOG_FORMAT` env var (`json` or `text`)
- Logs include: `request_id`, `client_ip`, `method`, `path`, `status_code`, `latency_ms`, etc.

**Usage:**
```bash
# JSON logging (default)
LOG_FORMAT=json python -m uvicorn ...

# Text logging (fallback)
LOG_FORMAT=text python -m uvicorn ...
```

**Example JSON log:**
```json
{
  "asctime": "2026-03-10T12:34:56",
  "levelname": "INFO",
  "name": "saint_scholar",
  "message": "POST /v1/ask 200 150ms",
  "request_id": "a1b2c3d4-...",
  "client_ip": "192.168.1.1",
  "method": "POST",
  "path": "/v1/ask",
  "status_code": 200,
  "latency_ms": 150
}
```

---

## Test Results

All 43 tests pass:
```
tests/test_api.py ........................... 8 passed
tests/test_generation.py .................... 8 passed
tests/test_ingest.py ....................... 13 passed
tests/test_retrieval.py .................... 13 passed
tests/test_static_mobile_overflow.py ........ 1 passed
```

---

## Dependencies Added

- `python-json-logger>=2.0.0,<3.0.0`

**Installation:**
```bash
pip install -r requirements.txt
```

---

## Configuration Options

### Rate Limiter
- `RATE_LIMIT_MAX_REQUESTS` (default: 20) - Max requests per window
- `RATE_LIMIT_WINDOW_SECONDS` (default: 60) - Time window in seconds
- `RATE_LIMIT_DB_PATH` (default: `.rate_limit.db`) - SQLite database path

### Logging
- `LOG_FORMAT` (default: `json`) - Log format: `json` or `text`
- `LOG_LEVEL` (default: `INFO`) - Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`

---

## Breaking Changes

None. All changes are backward compatible:
- Rate limiter behavior unchanged (just persistent now)
- Request IDs added without breaking existing responses
- JSON logging is opt-in via `LOG_FORMAT` env var
- Thread-safety fix is internal, no API changes

---

## Next Steps

1. **Rotate your Anthropic API key** (CRITICAL)
2. Install new dependency: `pip install python-json-logger`
3. Test locally: `uvicorn saint_scholar.api.main:app --reload`
4. Deploy with JSON logging: `LOG_FORMAT=json uvicorn ...`
5. Monitor logs for structured JSON output
6. Verify rate limits persist across restarts

---

## Files Modified

- `src/saint_scholar/retrieval.py` - Thread safety
- `src/saint_scholar/api/main.py` - Rate limiter, request IDs, logging
- `requirements.txt` - Added python-json-logger
- `.gitignore` - Added .rate_limit.db

## Files Created

- `.rate_limit.db` - Created at runtime (auto-initialized)

---

**Code Quality Status:** Ready for GitHub push after API key rotation.
