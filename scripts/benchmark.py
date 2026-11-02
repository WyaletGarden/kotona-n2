"""Repeatable HTTP/SQL sample. Refuses to write to an ordinary application server."""

import argparse
import json
import math
from pathlib import Path
import re
import secrets
from statistics import median
from time import perf_counter

import httpx


def benchmark(client, samples=10):
    marker = client.get("/api/test-environment")
    if marker.status_code != 200 or marker.json() != {"isolated": True}:
        raise RuntimeError("Start scripts.e2e_server with a disposable test database first.")
    results = {}
    state = {}
    csrf = ""

    def request(name, method, path, body=None):
        nonlocal csrf
        started = perf_counter()
        response = client.request(
            method,
            "/api" + path,
            json=body,
            headers={
                "X-CSRF-Token": csrf,
                "X-Revision": str(state.get("revision", 0)),
                **({"X-Compact-Response": "true"} if path == "/study/actions" else {}),
            },
        )
        elapsed = (perf_counter() - started) * 1000
        response.raise_for_status()
        data = response.json()
        if "csrf" in data:
            csrf = data["csrf"]
        if "revision" in data:
            state.update(data)
        if name:
            timing = dict(
                re.findall(r"(\w+);dur=([\d.]+)", response.headers.get("Server-Timing", ""))
            )
            results.setdefault(name, []).append(
                {
                    "http_ms": elapsed,
                    "app_ms": float(timing["app"]) if "app" in timing else None,
                    "sql_ms": float(timing["db"]) if "db" in timing else None,
                    "sql_queries": int(response.headers["X-SQL-Queries"])
                    if "X-SQL-Queries" in response.headers
                    else None,
                    "bytes": len(response.content),
                }
            )
        return data

    credentials = {
        "email": f"bench-{secrets.token_hex(8)}@example.com",
        "password": secrets.token_urlsafe(24),
    }
    request("register_first", "POST", "/auth/register", {**credentials, "name": "Benchmark"})
    # Retain separate endpoints to make comparisons across API versions possible.
    for _ in range(samples):
        request("identity", "GET", "/auth/me")
        request("workspace", "GET", "/workspace")
        request("words_50", "GET", "/words?limit=50")
    if client.get("/api/bootstrap").status_code == 200:
        for _ in range(samples):
            request("bootstrap", "GET", "/bootstrap")
    for _ in range(min(samples, 3)):
        request("login", "POST", "/auth/login", credentials)
    request(None, "GET", "/workspace")

    for mode in ("flash", "quiz"):
        request(
            "start_" + mode,
            "POST",
            "/study/sessions",
            {"mode": mode, "view": mode, "count": 0, "restart": True},
        )
        for _ in range(samples):
            study = state["session"]
            base = {"session_id": study["id"], "index": study["index"]}
            if mode == "flash":
                request("reveal", "POST", "/study/actions", {**base, "action": "reveal"})
                request(
                    "flash_answer",
                    "POST",
                    "/study/actions",
                    {**base, "action": "flash_answer", "correct": True},
                )
            else:
                request(
                    "quiz_answer",
                    "POST",
                    "/study/actions",
                    {**base, "action": "quiz_answer", "choice": study["current_word"]["reading"]},
                )
                request("next", "POST", "/study/actions", {**base, "action": "next"})

    summary = {}
    for name, rows in results.items():
        metrics = {}
        for key in rows[0]:
            values = sorted(row[key] for row in rows if row[key] is not None)
            if values:
                metrics[key] = {
                    "median": round(median(values), 2),
                    "p95": round(values[math.ceil(0.95 * len(values)) - 1], 2),
                }
        summary[name] = {"samples": len(rows), **metrics}
    return {
        "scope": "single HTTP client; isolated test account; not a concurrent load test",
        "results": summary,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        parser.error("--samples must be between 1 and 100")
    with httpx.Client(base_url=args.url, timeout=60) as client:
        report = benchmark(client, args.samples)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
