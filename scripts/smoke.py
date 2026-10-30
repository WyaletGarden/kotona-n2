"""HTTP regression and small latency/payload sample against the isolated E2E server."""

import json
import secrets
import statistics
import time
import httpx


def main():
    timings, sizes = [], []
    with httpx.Client(base_url="http://127.0.0.1:8010", timeout=20) as client:
        # Refuse to create a test user in an ordinary application server.
        marker = client.get("/api/test-environment")
        if marker.status_code != 200 or marker.json() != {"isolated": True}:
            raise SystemExit("Start scripts.e2e_server against a disposable test database first.")
        assert client.get("/api/health").json()["database"] == "ok"
        for asset in (
            "/",
            "/bootstrap.js",
            "/api.js",
            "/app.js",
            "/state.js",
            "/study-view.js",
            "/word-library.js",
            "/vocabulary-credits.html",
            "/openapi.json",
        ):
            assert client.get(asset).status_code == 200
        response = client.post(
            "/api/auth/register",
            json={
                "email": f"smoke-{secrets.token_hex(6)}@example.com",
                "name": "HTTP smoke",
                "password": secrets.token_urlsafe(24),
            },
        )
        assert response.status_code == 201, response.text
        csrf = response.json()["csrf"]
        state = client.get("/api/workspace").json()
        assert state["version"] == 2 and state["stats"]["total"] == state["catalogue"]["count"]

        def write(path, body):
            nonlocal state
            start = time.perf_counter()
            result = client.post(
                path,
                json=body,
                headers={"X-CSRF-Token": csrf, "X-Revision": str(state["revision"])},
            )
            assert result.is_success, result.text
            timings.append((time.perf_counter() - start) * 1000)
            sizes.append(len(result.content))
            state = result.json()

        write("/api/study/sessions", {"mode": "flash", "view": "flash", "count": 10})
        for _ in range(10):
            session = state["session"]
            write(
                "/api/study/actions",
                {"session_id": session["id"], "index": session["index"], "action": "reveal"},
            )
            write(
                "/api/study/actions",
                {
                    "session_id": session["id"],
                    "index": session["index"],
                    "action": "flash_answer",
                    "correct": True,
                },
            )
        assert state["session"]["status"] == "completed"
        assert "words" not in state and "ids" not in state["session"]
        page = client.get("/api/words?limit=50").json()
        assert len(page["items"]) == 50
        history = client.get("/api/study/history").json()
        assert history["items"][0]["answered_count"] == 10
        assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
        assert client.get("/api/workspace").status_code == 401
    print(
        json.dumps(
            {
                "requests": len(timings),
                "latency_median_ms": round(statistics.median(timings), 2),
                "latency_max_ms": round(max(timings), 2),
                "response_max_bytes": max(sizes),
                "scope": "single local HTTP client, ten flashcards; not a concurrent load test",
                "result": "passed",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
