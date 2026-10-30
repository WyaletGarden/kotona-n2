"""Capture/verify logical v1 records around migration without printing private data."""

import argparse
import json
import sys
from pathlib import Path
from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.db import engine, SessionLocal

SNAPSHOT = Path(".runtime/refactor-records.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    if args.capture:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
            data = {
                name: [
                    dict(row)
                    for row in connection.execute(text(f"SELECT * FROM {name}")).mappings()
                ]
                for name in ("users", "words", "study_sessions", "login_sessions")
            }
        SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        print("Captured original record counts:", {key: len(value) for key, value in data.items()})
        return
    from backend.models import LoginSession, StudyAnswer, StudySession, User, Word

    saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        for original in saved["words"]:
            word = db.get(Word, original["id"])
            assert word is not None
            for key in ("kanji", "reading", "meaning", "note", "seen", "correct", "user_id"):
                assert getattr(word, key) == original[key], f"Word field changed: {key}"
            assert word.marked_for_review == original["wrong"]
        for original in saved["users"]:
            user = db.get(User, original["id"])
            for key in (
                "email",
                "name",
                "password_hash",
                "revision",
                "view",
                "settings",
                "active_session_id",
            ):
                assert getattr(user, key) == original[key], f"Account field changed: {key}"
        for original in saved["study_sessions"]:
            study = db.get(StudySession, original["id"])
            data = original["data"]
            assert study.data["ids"] == data["ids"] and study.position == data["index"]
            assert study.correct == data["correct"]
            for answer in data["answers"]:
                current = db.get(StudyAnswer, (study.id, answer["index"]))
                assert current and current.correct == answer["correct"]
                for key in ("kanji", "reading", "meaning"):
                    if key in answer:
                        assert current.snapshot[key] == answer[key]
        for original in saved["login_sessions"]:
            assert db.get(LoginSession, original["token_hash"]) is not None
        assert len(list(db.scalars(select(Word)))) == len(saved["words"])
    print(
        "Verified all original words, private overrides, counters, account sessions and answer snapshots."
    )


if __name__ == "__main__":
    main()
