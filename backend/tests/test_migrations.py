"""Exercise the real v1 -> v2 -> v1 migration in a disposable PostgreSQL schema."""

from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from backend.catalogue import seed_words


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="PostgreSQL migration test")
def test_migration_preserves_private_data_and_active_answers():
    engine = sa.create_engine(os.environ["TEST_DATABASE_URL"])
    schema = "migration_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(
        os.environ["TEST_DATABASE_URL"], connect_args={"options": f"-csearch_path={schema}"}
    )
    user_id, word_id, first_id, active_id = [str(uuid4()) for _ in range(4)]
    date = datetime(2026, 10, 1, tzinfo=timezone.utc)
    sample = seed_words()[0]
    try:
        with isolated.connect() as connection:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "0001")
            metadata = sa.MetaData()
            users, words, sessions = [
                sa.Table(name, metadata, autoload_with=connection)
                for name in ("users", "words", "study_sessions")
            ]
            connection.execute(
                users.insert().values(
                    id=user_id,
                    email="legacy@example.com",
                    name="Legacy",
                    password_hash="unchanged-hash",
                    revision=12,
                    view="quiz",
                    settings={"count": 10, "quizType": "reading"},
                    active_session_id=active_id,
                    created_at=date,
                )
            )
            connection.execute(
                words.insert().values(
                    id=word_id,
                    user_id=user_id,
                    kanji=sample.kanji,
                    reading=sample.reading,
                    meaning="Nghĩa riêng cũ",
                    note="Ghi chú riêng cũ",
                    wrong=True,
                    seen=7,
                    correct=2,
                    created_at=date,
                )
            )
            for sid, ok, index, mode in (
                (first_id, False, 1, "flash"),
                (active_id, True, 0, "quiz"),
            ):
                data = {
                    "mode": mode,
                    "scope": "all",
                    "quizType": "reading",
                    "ids": [word_id],
                    "index": index,
                    "correct": int(ok),
                    "revealed": False,
                    "choice": sample.reading if mode == "quiz" else None,
                    "options": [sample.reading, "あ"],
                    "answers": [
                        {
                            "id": word_id,
                            "index": 0,
                            "correct": ok,
                            "kanji": sample.kanji,
                            "reading": sample.reading,
                            "meaning": "Nghĩa tại lúc học",
                        }
                    ],
                }
                connection.execute(
                    sessions.insert().values(
                        id=sid,
                        user_id=user_id,
                        data=data,
                        created_at=date if sid == first_id else date + timedelta(seconds=1),
                        completed_at=date if index else None,
                    )
                )
            connection.commit()
            command.upgrade(config, "head")
            metadata = sa.MetaData()
            tables = {
                name: sa.Table(name, metadata, autoload_with=connection)
                for name in (
                    "users",
                    "words",
                    "vocabulary",
                    "word_progress",
                    "study_sessions",
                    "study_answers",
                )
            }
            migrated = connection.execute(sa.select(tables["words"])).mappings().one()
            assert (
                migrated["id"] == word_id
                and migrated["meaning"] == "Nghĩa riêng cũ"
                and migrated["note"] == "Ghi chú riêng cũ"
            )
            assert migrated["vocabulary_id"] is not None
            assert (
                migrated["seen"] == 7
                and migrated["correct"] == 2
                and migrated["marked_for_review"] is True
            )
            user = connection.execute(sa.select(tables["users"])).mappings().one()
            assert (
                user["password_hash"] == "unchanged-hash"
                and user["revision"] == 12
                and user["active_session_id"] == active_id
            )
            progress = connection.execute(sa.select(tables["word_progress"])).mappings().one()
            assert (
                progress["skill"],
                progress["seen"],
                progress["correct"],
                progress["streak"],
            ) == ("reading", 2, 1, 1)
            active = (
                connection.execute(
                    sa.select(tables["study_sessions"]).where(
                        tables["study_sessions"].c.id == active_id
                    )
                )
                .mappings()
                .one()
            )
            assert (
                active["status"] == "in_progress"
                and active["position"] == 0
                and active["correct"] == 1
            )
            assert active["data"] == {"ids": [word_id]}
            assert (
                connection.scalar(sa.select(sa.func.count()).select_from(tables["study_answers"]))
                == 2
            )
            connection.commit()
            command.downgrade(config, "0001")
            metadata = sa.MetaData()
            restored = sa.Table("words", metadata, autoload_with=connection)
            record = connection.execute(sa.select(restored)).mappings().one()
            assert record["meaning"] == "Nghĩa riêng cũ" and record["note"] == "Ghi chú riêng cũ"
            assert record["seen"] == 7 and record["correct"] == 2 and record["wrong"] is True
            connection.commit()
            command.upgrade(config, "head")
            command.check(config)
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
