# Frontend Status and Plan

Last updated: 2026-03-04

## Current frontend in this repo

The shipped frontend is a static app served by FastAPI:
- `src/saint_scholar/api/static/index.html`
- `src/saint_scholar/api/static/app.js`
- `src/saint_scholar/api/static/styles.css`

This is the current MVP implementation and is already wired to live API endpoints.

## API contract currently consumed by the UI

- `GET /health`
- `GET /v1/figures`
- `POST /v1/ask`

`/v1/figures` response shape:

```json
{
  "figures": {
    "buddha": {
      "name": "Buddha",
      "tradition": "Buddhism",
      "tagline": "...",
      "icon": "...",
      "color": "#..."
    }
  }
}
```

`/v1/ask` request:

```json
{
  "question": "How does meditation physically change the brain?",
  "figure": "buddha"
}
```

`/v1/ask` response highlights:
- `answer`
- `citations[]` with `type` (`knowledge` or `style`), `score`, and metadata fields
- `meta` with `request_id`, `model`, token usage, latency, and retrieval counts

## Existing UX behavior

- Figure selection from `/v1/figures`.
- Character-count constrained input (`max_length=1200` aligned with API validation).
- Answer rendering with citation display.
- Health badge and request metadata display.
- Theme toggle and conversation-style interface.

## Near-term polish backlog (without framework migration)

1. Add clearer loading/skeleton states for first response.
2. Improve error-state mapping for `400`, `401`, `503`, `500` responses.
3. Add accessibility pass (focus states, keyboard nav, ARIA labels audit).
4. Add end-to-end smoke check for core browser flow.

## Optional migration path (only if needed)

A framework migration (for example Next.js) is optional, not required for current functionality. Consider it only when one of these becomes necessary:
- multi-page marketing/content workflows
- team-scale component architecture needs
- SSR/SEO requirements
- more advanced client-side state and routing complexity

If migration is chosen, keep API contracts identical to reduce risk.
