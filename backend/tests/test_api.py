import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import Account
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.catalogue import seed_words
from backend.config import settings
from backend.constants import MAX_WORDS, REQUEST_BYTES
from backend.main import app
from backend.models import AuthAttempt, LoginSession, User, Vocabulary, Word, now

SEED_COUNT = len(seed_words())
WORD = {"kanji": "記憶", "reading": "きおく", "meaning": "Trí nhớ", "note": "記憶に残る。"}


def add_review_word(account):
    response = account.write("POST", "/words", WORD)
    assert response.status_code == 201, response.text
    word = response.json()["updated_words"][0]
    assert (
        account.write(
            "PATCH", f"/words/{word['id']}/review", {"marked_for_review": True}
        ).status_code
        == 200
    )
    return word


def test_auth_and_private_cookie(account, database):
    assert account.state["stats"]["total"] == SEED_COUNT
    assert account.state["version"] == 2 and "words" not in account.state
    with database() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2")
        assert db.scalar(select(LoginSession)).token_hash != account.client.cookies.get(
            "kotoba_session"
        )
    response = account.client.post("/api/auth/logout", headers={"X-CSRF-Token": account.csrf})
    assert response.status_code == 204
    assert account.client.get("/api/workspace").status_code == 401
    response = account.client.post(
        "/api/auth/login", json={"email": account.email.upper(), "password": "strong-password-123"}
    )
    assert response.status_code == 200
    assert (
        "HttpOnly" in response.headers["set-cookie"]
        and "SameSite=lax" in response.headers["set-cookie"]
    )


def test_csrf_origin_validation_and_request_limit(account):
    client = account.client
    assert client.post("/api/words", json=WORD).status_code == 403
    assert (
        client.post("/api/words", json=WORD, headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    for bad in (
        {**WORD, "reading": "kioku"},
        {**WORD, "meaning": " "},
        {**WORD, "user_id": "forged"},
    ):
        assert account.write("POST", "/words", bad).status_code == 422
    assert account.reload()["revision"] == 0
    assert client.get("/api/workspace").headers["cache-control"] == "no-store"
    assert client.post("/api/auth/login", content=b"x" * (REQUEST_BYTES + 1)).status_code == 413

    def chunks():
        for _ in range(5):
            yield b"x" * 1_000_000

    assert (
        client.post(
            "/api/auth/login", content=chunks(), headers={"Content-Type": "application/json"}
        ).status_code
        == 413
    )


def test_pagination_search_duplicate_import_export(account):
    assert account.write("POST", "/words", WORD).status_code == 201
    word = account.state["updated_words"][0]
    duplicate = account.write("POST", "/words", WORD)
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "duplicate_word"
    search = account.page(q="tri nho")
    assert word["id"] in {w["id"] for w in search["items"]}
    assert account.page(limit=3, offset=1)["total"] == SEED_COUNT + 1
    assert len(account.page(limit=3, offset=1)["items"]) == 3
    assert account.page(q="%")["total"] == 0  # Wildcards are literal input.
    assert account.write("POST", "/words/import", {"words": [WORD, WORD]}).json()["duplicates"] == 2
    before_revision = account.state["revision"]
    preview = account.client.post(
        "/api/words/import/preview", json={"words": [WORD]}, headers={"X-CSRF-Token": account.csrf}
    )
    assert preview.json()["added"] == 0
    assert account.reload()["revision"] == before_revision
    assert len(account.client.get("/api/words/export").json()) == SEED_COUNT + 1
    assert account.write("DELETE", f"/words/{word['id']}").status_code == 200
    assert account.state["stats"]["total"] == SEED_COUNT


def test_shared_dictionary_preserves_private_overrides(account, database):
    first = account.page(limit=1)["items"][0]
    payload = {key: first[key] for key in ("kanji", "reading", "meaning", "note")}
    payload["meaning"] = "Nghĩa riêng của tài khoản A"
    assert account.write("PUT", f"/words/{first['id']}", payload).status_code == 200
    with TestClient(app) as client:
        second = Account(client, "other@example.com")
        assert second.write("DELETE", f"/words/{first['id']}").status_code == 404
        assert second.write("PUT", f"/words/{first['id']}", WORD).status_code == 404
        other = next(
            w for w in second.page(q=first["kanji"])["items"] if w["reading"] == first["reading"]
        )
        assert other["meaning"] == first["meaning"]
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Vocabulary)) == SEED_COUNT
        assert db.scalar(select(func.count()).select_from(Word)) == SEED_COUNT * 2
        assert (
            db.scalar(select(func.count()).select_from(Word).where(Word.meaning_override.is_(None)))
            == SEED_COUNT * 2 - 1
        )


def test_marking_review_cannot_create_mastery(account):
    word = add_review_word(account)
    account.start(scope="wrong", view="review")
    account.flash(False)
    result = account.write(
        "PATCH", f"/words/{word['id']}/review", {"marked_for_review": False}
    ).json()["updated_words"][0]
    assert result["correct"] == 0 and result["known"] is False
    assert result["marked_for_review"] is False and result["needs_review"] is True
    assert account.state["stats"]["known"] == 0


def test_mastery_tracks_both_skills_and_manual_mark_independently(account):
    word = add_review_word(account)
    for skill in ("reading", "meaning"):
        for _ in range(2):
            account.start(scope="wrong", view="review", quizType=skill, restart=True)
            account.flash(True)
    result = account.write(
        "PATCH", f"/words/{word['id']}/review", {"marked_for_review": False}
    ).json()["updated_words"][0]
    assert result["known"] is True
    assert result["progress"]["reading"]["streak"] == result["progress"]["meaning"]["streak"] == 2
    assert account.state["stats"]["known"] == 1
    assert (
        account.write("PATCH", f"/words/{word['id']}/review", {"marked_for_review": True}).json()[
            "updated_words"
        ][0]["known"]
        is True
    )


def test_edits_reset_only_affected_progress_and_notes_preserve_session(account):
    word = add_review_word(account)
    for skill in ("reading", "meaning"):
        account.start(scope="wrong", view="review", quizType=skill, restart=True)
        account.flash(True)
    account.start(scope="wrong", view="review", restart=True)
    active_id = account.state["session"]["id"]
    payload = {**WORD, "note": "Ghi chú mới"}
    response = account.write("PUT", f"/words/{word['id']}", payload)
    assert response.json()["session"]["id"] == active_id
    response = account.write("PUT", f"/words/{word['id']}", {**payload, "meaning": "Ký ức"})
    updated = response.json()["updated_words"][0]
    assert updated["progress"]["reading"]["seen"] == 1
    assert updated["progress"]["meaning"]["seen"] == 0
    response = account.write(
        "PUT", f"/words/{word['id']}", {**payload, "kanji": "記録", "reading": "きろく"}
    )
    assert response.json()["session"] is None
    assert response.json()["updated_words"][0]["seen"] == 0
    assert response.json()["updated_words"][0]["correct"] == 0


def test_switch_modes_resumes_previous_session(account):
    first = account.start()
    account.action("reveal")
    account.start(mode="quiz", view="quiz")
    resumed = account.start(mode="flash", view="flash")
    assert resumed["id"] == first["id"] and resumed["revealed"] is True
    history = account.client.get("/api/study/history").json()
    assert history["total"] == 2 and {s["status"] for s in history["items"]} == {
        "paused",
        "in_progress",
    }
    quiz = next(s for s in history["items"] if s["mode"] == "quiz")
    assert (
        account.write("POST", f"/study/sessions/{quiz['id']}/resume").json()["session"]["id"]
        == quiz["id"]
    )


@pytest.mark.parametrize("mode", ["flash", "quiz"])
def test_review_skips_empty_sessions_when_words_become_due(account, mode):
    empty = account.start(mode=mode, scope="wrong", view="review")
    assert empty["total"] == 0
    account.start()
    word_id = account.state["session"]["current_word"]["id"]
    account.flash(False)
    assert account.state["stats"]["review"] == 1
    assert account.page(status="review")["items"][0]["id"] == word_id

    review = account.start(mode=mode, scope="wrong", view="review")
    assert review["id"] != empty["id"]
    assert review["total"] == 1 and review["current_word"]["id"] == word_id


def test_legacy_empty_review_session_is_not_resumed(account, database):
    from backend.models import StudySession

    empty = account.start(scope="wrong", view="review")
    account.start()
    with database.begin() as db:
        db.get(StudySession, empty["id"]).status = "paused"
    assert account.write("POST", f"/study/sessions/{empty['id']}/resume").status_code == 409
    account.flash(False)
    review = account.start(scope="wrong", view="review")
    assert review["id"] != empty["id"] and review["total"] == 1


def test_quiz_rejects_forged_action_and_duplicate_scoring(account):
    s = account.start(mode="quiz", view="quiz")
    correct = s["current_word"]["reading"]
    wrong = next(v for v in s["options"] if v != correct)
    assert account.action("quiz_answer", choice=wrong, correct=True).status_code == 422
    assert account.action("flash_answer", correct=True).status_code == 422
    assert account.action("next").status_code == 422
    response = account.action("quiz_answer", choice=wrong)
    assert response.status_code == 200 and account.state["session"]["correct"] == 0
    assert len(response.content) < 12_000
    assert "words" not in response.json() and "ids" not in response.json()["session"]
    assert account.action("quiz_answer", choice=correct).status_code == 409
    assert account.state["updated_words"][0]["seen"] == 1
    assert account.action("next").status_code == 200
    assert account.state["session"]["index"] == 1


def test_history_keeps_answer_snapshot_after_edit_and_delete(account):
    word = add_review_word(account)
    s = account.start(scope="wrong", view="review")
    account.flash(True)
    account.write("DELETE", f"/words/{word['id']}")
    history = account.client.get("/api/study/history").json()
    assert history["items"][0]["status"] == "completed"
    answers = account.client.get(f"/api/study/sessions/{s['id']}/answers").json()
    assert answers["total"] == 1
    assert answers["items"][0]["kanji"] == WORD["kanji"]
    assert answers["items"][0]["meaning"] == WORD["meaning"]


def test_revision_conflicts_and_invalid_ids_do_not_change_data(account):
    account.write("POST", "/words", WORD)
    assert account.write("DELETE", f"/words/{uuid4()}", revision=0).status_code == 409
    assert account.write("DELETE", "/words/not-a-uuid").status_code == 422
    assert account.reload()["revision"] == 1
    assert account.state["stats"]["total"] == SEED_COUNT + 1


def test_start_schema_rejects_incoherent_view_and_boolean_count(account):
    for body in (
        {"mode": "quiz", "view": "flash"},
        {"scope": "wrong", "view": "flash"},
        {"count": False},
    ):
        assert account.write("POST", "/study/sessions", body).status_code == 422
    assert account.reload()["revision"] == 0


def test_import_atomicity_capacity_and_expired_auth(account, database):
    assert (
        account.write(
            "POST", "/words/import", {"words": [WORD, {**WORD, "reading": "abc"}]}
        ).status_code
        == 422
    )
    rows = [{**WORD, "kanji": f"単語{i}"} for i in range(MAX_WORDS - SEED_COUNT + 1)]
    assert account.write("POST", "/words/import", {"words": rows}).status_code == 422
    assert account.reload()["stats"]["total"] == SEED_COUNT
    with database.begin() as db:
        db.scalar(select(LoginSession)).expires_at = now() - timedelta(seconds=1)
    assert account.client.get("/api/auth/me").status_code == 401


def test_failed_logins_consume_rate_limit(client, database, monkeypatch):
    monkeypatch.setattr(settings(), "auth_limit", 3)
    for code in (401, 401, 401, 429):
        response = client.post(
            "/api/auth/login",
            json={"email": "absent@example.com", "password": "wrong-password-123"},
        )
        assert response.status_code == code
    assert response.headers["retry-after"] == "900"
    with database() as db:
        assert db.scalar(select(AuthAttempt)).count == 3


def test_response_validation_rolls_back_write(account, database, monkeypatch):
    import backend.routes.words as route

    monkeypatch.setattr(route, "mutation", lambda *args, **kwargs: {})
    with pytest.raises(ResponseValidationError):
        account.write("POST", "/words", WORD)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Word)) == SEED_COUNT
        assert db.scalar(select(User)).revision == 0


def test_commit_failure_is_not_reported_as_success(account, monkeypatch):
    from backend.services import words

    original = words.add_word

    def marked(db, user, payload):
        result = original(db, user, payload)
        db.info["fail_commit"] = True
        return result

    def fail(db):
        if db.info.get("fail_commit"):
            raise SQLAlchemyError("simulated commit failure")

    monkeypatch.setattr(words, "add_word", marked)
    event.listen(Session, "before_commit", fail)
    try:
        response = account.write("POST", "/words", WORD)
        assert response.status_code == 503
    finally:
        event.remove(Session, "before_commit", fail)
    assert account.reload()["stats"]["total"] == SEED_COUNT
    assert account.state["revision"] == 0


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="PostgreSQL row locks required")
def test_parallel_writes_have_single_winner(account):
    headers = {"X-CSRF-Token": account.csrf, "X-Revision": str(account.state["revision"])}
    cookies = dict(account.client.cookies)

    def write(i):
        with TestClient(app) as client:
            client.cookies.update(cookies)
            return client.post(
                "/api/words", json={**WORD, "kanji": f"並行{i}"}, headers=headers
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, [1, 2])) == [201, 409]
