# Local Testing Guide

## ✅ Server Status

The Saint & Scholar API is currently running on **http://127.0.0.1:8000**

All 5 critical fixes have been verified and are working:

---

## 🧪 Verified Fixes

### 1. ✅ Thread-Safety
- Added `threading.RLock()` to `_RESOURCES` in `retrieval.py`
- Prevents crashes under concurrent reindex operations

### 2. ✅ Persistent Rate Limiter
- SQLite database created at `.rate_limit.db` (16KB)
- Database entries: 1 (and growing with each request)
- Rate limits now survive server restarts

### 3. ✅ Request ID Tracking
- Every response includes `X-Request-ID` header
- Example: `x-request-id: 720f0cf8-ebd1-49b4-9c25-8014a85d65e2`
- Request IDs are included in all logs

### 4. ✅ Structured JSON Logging
- Logs in JSON format with structured fields:
  - `request_id`, `client_ip`, `method`, `path`, `status_code`, `latency_ms`
- Example log entry:
```json
{
  "asctime": "2026-03-10 10:26:04,921",
  "levelname": "INFO",
  "message": "GET /health 200 4ms",
  "request_id": "720f0cf8-ebd1-49b4-9c25-8014a85d65e2",
  "client_ip": "127.0.0.1",
  "method": "GET",
  "path": "/health",
  "status_code": 200,
  "latency_ms": 4
}
```

### 5. ✅ .gitignore Protection
- `.env` is properly excluded (line 2)
- `.rate_limit.db` is excluded (line 14)

---

## 🧪 Test Commands

### Test 1: Health Check (with Request ID)
```bash
curl -i http://127.0.0.1:8000/health
```
**Expected:** Response includes `X-Request-ID` header

### Test 2: List Available Figures
```bash
curl -s http://127.0.0.1:8000/v1/figures | python -m json.tool
```
**Expected:** JSON response with all available figures (buddha, aurelius, etc.)

### Test 3: View Home Page
```bash
curl -s http://127.0.0.1:8000/ | head -20
```
**Expected:** HTML content of the Saint & Scholar web interface

### Test 4: Check Structured Logs
```bash
# View recent JSON logs
tail -20 C:\Users\mjbar\AppData\Local\Temp\claude\C--Users-mjbar-dev-saint-scholar\tasks\bb836aa.output | grep -E '^\{'
```
**Expected:** JSON-formatted log entries with request_id, client_ip, etc.

### Test 5: Verify Rate Limiter Database
```bash
cd /c/Users/mjbar/dev/saint-scholar
python -c "import sqlite3; conn = sqlite3.connect('.rate_limit.db'); cursor = conn.execute('SELECT COUNT(*) FROM rate_limits'); print(f'Rate limiter entries: {cursor.fetchone()[0]}'); conn.close()"
```
**Expected:** Shows number of rate limit entries in database

### Test 6: Test Rate Limiting (requires ANTHROPIC_API_KEY)
```bash
# Make 25 rapid requests to trigger rate limit (default: 20 req/60s)
for i in {1..25}; do
  curl -s http://127.0.0.1:8000/v1/ask \
    -H "Content-Type: application/json" \
    -d '{"question":"What is wisdom?","figure":"buddha"}' &
done
wait
```
**Expected:** Some requests will return 429 status with rate limit error

---

## 🌐 Web Interface

Open in browser: **http://127.0.0.1:8000**

The web interface should load with:
- Dropdown to select a figure (Buddha, Marcus Aurelius, etc.)
- Text area for questions
- "Ask" button
- Citation panel and info panel

**Note:** /v1/ask endpoint requires `ANTHROPIC_API_KEY` to be set in `.env` file.

---

## 🔍 Monitoring

### View Live Logs
```bash
tail -f C:\Users\mjbar\AppData\Local\Temp\claude\C--Users-mjbar-dev-saint-scholar\tasks\bb836aa.output
```

### Parse JSON Logs
```bash
# Pretty-print JSON logs
tail -100 C:\Users\mjbar\AppData\Local\Temp\claude\C--Users-mjbar-dev-saint-scholar\tasks\bb836aa.output | \
  grep -E '^\{' | \
  python -m json.tool
```

### Check Request IDs
```bash
# Extract all request IDs from logs
grep -oP '"request_id": "\K[^"]+' C:\Users\mjbar\AppData\Local\Temp\claude\C--Users-mjbar-dev-saint-scholar\tasks\bb836aa.output
```

---

## 🛑 Stop Server

To stop the server:
```bash
# Find the process
ps aux | grep uvicorn

# Kill it (replace PID with actual process ID)
kill <PID>
```

Or in Claude Code:
```
Use TaskStop tool with task_id: bb836aa
```

---

## 📊 Test Results Summary

All automated tests passed: **43/43 tests ✅**

- API tests: 8/8 ✅
- Generation tests: 8/8 ✅
- Ingest tests: 13/13 ✅
- Retrieval tests: 13/13 ✅
- UI tests: 1/1 ✅

---

## ⚠️ Current Status

**Degraded Mode** (expected):
- ❌ `ANTHROPIC_API_KEY` is not set in `.env`
- ✅ Vector store is ready
- ✅ All other services operational

To enable full functionality, set `ANTHROPIC_API_KEY` in `.env` file.

---

## 🔧 Configuration

Current environment variables:
- `LOG_FORMAT=json` - Structured JSON logging enabled
- `LOG_LEVEL=INFO` - Info-level logging
- `RATE_LIMIT_MAX_REQUESTS=20` - Max 20 requests per window
- `RATE_LIMIT_WINDOW_SECONDS=60` - 60-second rate limit window

To change log format to text:
```bash
LOG_FORMAT=text python -m uvicorn saint_scholar.api.main:app --reload
```

---

## 📝 Next Steps

1. ✅ All critical fixes implemented and tested
2. ⚠️ **Rotate your Anthropic API key** (CRITICAL - not yet done)
3. ✅ Ready for GitHub push (after key rotation)
4. Test production deployment with `deploy/deploy.sh`
5. Monitor logs in production for structured JSON output

---

**Status:** All fixes verified ✅ | Server running ✅ | Tests passing ✅
