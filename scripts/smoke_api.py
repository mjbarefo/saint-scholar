#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def _request_json(
    *,
    method: str,
    url: str,
    timeout: float,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url=url, method=method, headers=headers, data=data)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(response.status)
        body = response.read().decode("utf-8")
        return status, json.loads(body)


def _fail(message: str, *, detail: str | None = None) -> int:
    print(f"FAIL: {message}")
    if detail:
        print(f"      {detail}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Saint & Scholar API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument(
        "--figure",
        default="",
        help="Figure id to test (defaults to first available from /v1/figures).",
    )
    parser.add_argument(
        "--question",
        default="How does meditation physically change the brain?",
        help="Question for /v1/ask",
    )
    parser.add_argument("--timeout", type=float, default=25.0, help="Request timeout in seconds")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Running smoke test against: {base_url}")

    try:
        status, health = _request_json(method="GET", url=f"{base_url}/health", timeout=args.timeout)
        if status != 200 or health.get("status") != "ok":
            return _fail("/health returned unexpected response", detail=str(health))
        print("PASS: /health")
    except urllib.error.URLError as exc:
        return _fail("/health unreachable", detail=str(exc))
    except Exception as exc:  # pragma: no cover
        return _fail("/health failed", detail=str(exc))

    try:
        status, figures_payload = _request_json(
            method="GET", url=f"{base_url}/v1/figures", timeout=args.timeout
        )
        figures = figures_payload.get("figures", {})
        if status != 200 or not isinstance(figures, dict) or not figures:
            return _fail("/v1/figures returned empty or invalid response", detail=str(figures_payload))
        print(f"PASS: /v1/figures ({len(figures)} figures)")
    except Exception as exc:  # pragma: no cover
        return _fail("/v1/figures failed", detail=str(exc))

    selected_figure = args.figure.strip() or next(iter(figures.keys()))
    if selected_figure not in figures:
        return _fail(
            "Requested figure is not available",
            detail=f"figure={selected_figure}, available={', '.join(figures.keys())}",
        )
    print(f"Using figure: {selected_figure}")

    payload = {"question": args.question, "figure": selected_figure}
    try:
        status, ask_response = _request_json(
            method="POST",
            url=f"{base_url}/v1/ask",
            timeout=args.timeout,
            payload=payload,
        )
        if status != 200:
            return _fail("/v1/ask returned non-200", detail=str(ask_response))

        answer = str(ask_response.get("answer", "")).strip()
        citations = ask_response.get("citations", [])
        meta = ask_response.get("meta", {})

        if not answer:
            return _fail("/v1/ask missing answer text")
        if not isinstance(citations, list) or not citations:
            return _fail("/v1/ask returned no citations")
        if not isinstance(meta, dict) or not meta.get("request_id"):
            return _fail("/v1/ask missing meta.request_id")

        print(
            "PASS: /v1/ask "
            f"(citations={len(citations)}, latency_ms={meta.get('latency_ms', 'n/a')}, "
            f"model={meta.get('model', 'n/a')})"
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return _fail("/v1/ask returned HTTP error", detail=f"status={exc.code}, body={body}")
    except Exception as exc:  # pragma: no cover
        return _fail("/v1/ask failed", detail=str(exc))

    print("Smoke test succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
