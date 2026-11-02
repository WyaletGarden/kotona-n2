"""Behavior and SQL budgets for the remote-database hot paths."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.config import settings
from backend.models import LoginSession, User, Word, WordProgress, now


def test_bootstrap_anonymous_and_expired_cookie(client, database, monkeypatch):
    monkeypatch.setattr(settings(), "performance_metrics", True)
    result = client.get("/api/bootstrap")
    assert result.status_code == 200
    assert result.json()["catalogue"]["count"] > 0
    assert result.json()["identity"] is None
    assert result.json()["workspace"] is None
    assert result.headers["X-SQL-Queries"] == "0"
    from conftest import Account

    Account(client)
    with database.begin() as db:
        db.scalar(select(LoginSession)).expires_at = now() - timedelta(seconds=1)
    result = client.get("/api/bootstrap")
    assert result.json()["identity"] is None and result.json()["workspace"] is None


def test_bootstrap_and_compact_study_query_budgets(account, monkeypatch):
    monkeypatch.setattr(settings(), "performance_metrics", True)
    identity = account.client.get("/api/auth/me")
    assert int(identity.headers["X-SQL-Queries"]) == 1
    initial = account.client.get("/api/bootstrap")
    assert initial.json()["identity"]["csrf"] == account.csrf
    assert initial.json()["workspace"]["stats"] == account.state["stats"]
    assert int(initial.headers["X-SQL-Queries"]) == 2
    assert "password_hash" not in initial.text

    account.start(count=10)
    session = account.state["session"]
    response = account.client.post(
        "/api/study/actions",
        json={"session_id": session["id"], "index": session["index"], "action": "reveal"},
        headers={
            "X-CSRF-Token": account.csrf,
            "X-Revision": str(account.state["revision"]),
            "X-Compact-Response": "true",
        },
    )
    assert response.status_code == 200
    assert response.json()["session"]["revealed"] is True
    assert "stats" not in response.json() and "settings" not in response.json()
    assert int(response.headers["X-SQL-Queries"]) <= 8
    assert "Server-Timing" in response.headers
    account.state.update(response.json())
    assert account.action("flash_answer", correct=True).status_code == 200
    assert account.state["stats"]["new"] == initial.json()["workspace"]["stats"]["new"] - 1


def test_review_statistics_expire_without_a_revision_change(account, database, monkeypatch):
    from backend import repositories

    clock = now()
    due = clock + timedelta(seconds=10)
    with database.begin() as db:
        word = db.scalar(select(Word).limit(1))
        db.add(
            WordProgress(
                word_id=word.id,
                skill="reading",
                seen=1,
                correct=1,
                streak=1,
                last_correct=True,
                next_review_at=due,
            )
        )
    monkeypatch.setattr(repositories, "now", lambda: clock)
    before = account.reload()
    assert before["stats"]["review"] == 0
    assert before["stats"]["valid_until"] is not None
    assert 0 <= before["stats"]["refresh_after_ms"] <= 10000
    monkeypatch.setattr(repositories, "now", lambda: due + timedelta(seconds=1))
    after = account.reload()
    assert after["revision"] == before["revision"]
    assert after["stats"]["review"] == 1
    assert after["stats"]["valid_until"] is None
    assert after["stats"]["refresh_after_ms"] is None


def test_performance_headers_are_opt_in(client, monkeypatch):
    monkeypatch.setattr(settings(), "performance_metrics", False)
    result = client.get("/api/bootstrap")
    assert "X-SQL-Queries" not in result.headers
    assert "Server-Timing" not in result.headers


def test_compact_quiz_keeps_wrong_answers_and_completion_consistent(account):
    session = account.start(mode="quiz", view="quiz", count=10)
    wrong = next(
        option for option in session["options"] if option != session["current_word"]["reading"]
    )
    assert account.action("quiz_answer", choice=wrong).status_code == 200
    assert account.state["session"]["current_result"] is False
    assert account.state["session"]["answered_count"] == 1
    result = account.client.post(
        "/api/study/actions",
        json={"session_id": session["id"], "index": 0, "action": "next"},
        headers={
            "X-CSRF-Token": account.csrf,
            "X-Revision": str(account.state["revision"]),
            "X-Compact-Response": "true",
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert "stats" not in body
    assert body["session"]["index"] == 1
    assert body["session"]["current_result"] is None
    assert body["session"]["answered"] is False
    assert body["session"]["answered_count"] == 1
    assert body["session"]["correct"] == 0


def test_missing_active_session_does_not_block_bootstrap(account, database):
    with database.begin() as db:
        db.scalar(select(User)).active_session_id = str(uuid4())
    result = account.client.get("/api/bootstrap")
    assert result.status_code == 200
    assert result.json()["identity"] is not None
    assert result.json()["workspace"]["session"] is None


def test_benchmark_refuses_an_ordinary_application_server(client, database):
    from scripts.benchmark import benchmark

    with pytest.raises(RuntimeError, match="disposable test database"):
        benchmark(client, samples=1)
    with database() as db:
        assert db.scalar(select(User)) is None
