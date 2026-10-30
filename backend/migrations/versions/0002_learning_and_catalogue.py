"""Shared definitions, skill progress and resumable normalized study sessions.

Word IDs, private overrides, old counters, account sessions and answer snapshots
are preserved. Historical flashcard answers are assigned to reading, the skill
the old flashcard screen asked the learner to recall.
"""

from datetime import timedelta
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None
json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def tables(connection):
    metadata = sa.MetaData()
    return {
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


def upgrade():
    op.create_table(
        "vocabulary",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kanji", sa.String(80), nullable=False),
        sa.Column("reading", sa.String(120), nullable=False),
        sa.Column("meaning", sa.String(300), nullable=False),
        sa.Column("note", sa.String(600), nullable=False),
        sa.Column("source_key", sa.String(80), nullable=False),
        sa.UniqueConstraint("kanji", "reading", name="uq_vocabulary_key"),
    )
    with op.batch_alter_table("words") as batch:
        batch.alter_column("wrong", new_column_name="marked_for_review", existing_type=sa.Boolean())
        batch.alter_column("meaning", nullable=True, existing_type=sa.String(300))
        batch.alter_column("note", nullable=True, existing_type=sa.String(600))
        batch.add_column(sa.Column("vocabulary_id", sa.String(36)))
        batch.add_column(sa.Column("search_text", sa.Text(), nullable=True))
        batch.create_foreign_key("fk_words_vocabulary", "vocabulary", ["vocabulary_id"], ["id"])
        batch.create_index("ix_words_vocabulary_id", ["vocabulary_id"])
        batch.create_index("ix_words_user_created", ["user_id", "created_at", "id"])
    op.create_table(
        "word_progress",
        sa.Column(
            "word_id",
            sa.String(36),
            sa.ForeignKey("words.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("skill", sa.String(16), primary_key=True),
        sa.Column("seen", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.Column("last_correct", sa.Boolean()),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "seen >= 0 AND correct >= 0 AND correct <= seen AND streak >= 0",
            name="ck_progress_counts",
        ),
        sa.CheckConstraint("skill IN ('reading', 'meaning')", name="ck_progress_skill"),
    )
    with op.batch_alter_table("study_sessions") as batch:
        for name in ("mode", "scope", "skill", "status"):
            batch.add_column(sa.Column(name, sa.String(16)))
        for name in ("position", "total", "correct"):
            batch.add_column(sa.Column(name, sa.Integer()))
        batch.add_column(sa.Column("revealed", sa.Boolean()))
        batch.add_column(sa.Column("choice", sa.String(300)))
        batch.add_column(sa.Column("options", json_type))
    op.create_table(
        "study_answers",
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("study_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("word_id", sa.String(36), sa.ForeignKey("words.id", ondelete="SET NULL")),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("choice", sa.String(300)),
        sa.Column("snapshot", json_type, nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
    )
    connection = op.get_bind()
    t = tables(connection)
    from backend.catalogue import vocabulary_records
    from backend.normalization import search_text

    catalogue = list(vocabulary_records())
    connection.execute(t["vocabulary"].insert(), catalogue)
    canonical = {(w["kanji"], w["reading"]): w for w in catalogue}
    old_words = {w["id"]: dict(w) for w in connection.execute(sa.select(t["words"])).mappings()}
    for word in old_words.values():
        shared = canonical.get((word["kanji"], word["reading"]))
        values = {"search_text": search_text(word["kanji"], word["reading"], word["meaning"])}
        if shared:
            values["vocabulary_id"] = shared["id"]
            if word["meaning"] == shared["meaning"]:
                values["meaning"] = None
            if word["note"] == shared["note"]:
                values["note"] = None
        connection.execute(
            t["words"].update().where(t["words"].c.id == word["id"]).values(**values)
        )
    active = dict(
        connection.execute(sa.select(t["users"].c.id, t["users"].c.active_session_id))
        .tuples()
        .all()
    )
    progress = {}
    sessions = (
        connection.execute(
            sa.select(t["study_sessions"]).order_by(
                t["study_sessions"].c.created_at, t["study_sessions"].c.id
            )
        )
        .mappings()
        .all()
    )
    for row in sessions:
        data = row["data"]
        ids = data.get("ids", [])
        skill = data.get("quizType", "reading")
        answered = data.get("answers", [])
        position = min(data.get("index", 0), len(ids))
        completed = row["completed_at"] is not None or bool(ids) and position == len(ids)
        status = (
            "completed"
            if completed
            else "in_progress"
            if active.get(row["user_id"]) == row["id"]
            else "paused"
        )
        if not completed and any(w not in old_words for w in ids):
            status = "invalidated"
        connection.execute(
            t["study_sessions"]
            .update()
            .where(t["study_sessions"].c.id == row["id"])
            .values(
                data={"ids": ids},
                mode=data.get("mode", "flash"),
                scope=data.get("scope", "all"),
                skill=skill,
                status=status,
                position=position,
                total=len(ids),
                correct=sum(bool(a["correct"]) for a in answered),
                revealed=bool(data.get("revealed")),
                choice=data.get("choice"),
                options=data.get("options", []),
            )
        )
        for answer in answered:
            word = old_words.get(answer["id"])
            snapshot = {
                key: answer.get(key, word.get(key, "") if word else "")
                for key in ("kanji", "reading", "meaning")
            }
            connection.execute(
                t["study_answers"]
                .insert()
                .values(
                    session_id=row["id"],
                    position=answer["index"],
                    word_id=word["id"] if word else None,
                    correct=bool(answer["correct"]),
                    choice=data.get("choice") if answer["index"] == data.get("index") else None,
                    snapshot=snapshot,
                    answered_at=row["created_at"],
                )
            )
            if word:
                p = progress.setdefault(
                    (word["id"], skill),
                    dict(word_id=word["id"], skill=skill, seen=0, correct=0, streak=0),
                )
                ok = bool(answer["correct"])
                p["seen"] += 1
                p["correct"] += int(ok)
                p["streak"] = p["streak"] + 1 if ok else 0
                p["last_correct"] = ok
                p["next_review_at"] = row["created_at"] + (
                    timedelta(days=(1, 3, 7, 14, 30)[min(p["streak"] - 1, 4)])
                    if ok
                    else timedelta(minutes=10)
                )
    if progress:
        connection.execute(t["word_progress"].insert(), list(progress.values()))
    with op.batch_alter_table("words") as batch:
        batch.alter_column("search_text", nullable=False, existing_type=sa.Text())
    with op.batch_alter_table("study_sessions") as batch:
        for name in ("mode", "scope", "skill", "status"):
            batch.alter_column(name, nullable=False, existing_type=sa.String(16))
        for name in ("position", "total", "correct"):
            batch.alter_column(name, nullable=False, existing_type=sa.Integer())
        batch.alter_column("revealed", nullable=False, existing_type=sa.Boolean())
        batch.alter_column("options", nullable=False, existing_type=json_type)
        batch.create_check_constraint(
            "ck_session_counts",
            "position >= 0 AND correct >= 0 AND correct <= total AND position <= total",
        )
        batch.create_check_constraint(
            "ck_session_status",
            "status IN ('in_progress','paused','completed','abandoned','invalidated')",
        )
        batch.create_index("ix_sessions_resume", ["user_id", "status", "mode", "scope", "skill"])


def downgrade():
    connection = op.get_bind()
    t = tables(connection)
    shared = {w["id"]: w for w in connection.execute(sa.select(t["vocabulary"])).mappings()}
    for word in connection.execute(sa.select(t["words"])).mappings().all():
        definition = shared.get(word["vocabulary_id"], {})
        connection.execute(
            t["words"]
            .update()
            .where(t["words"].c.id == word["id"])
            .values(
                meaning=word["meaning"]
                if word["meaning"] is not None
                else definition.get("meaning", ""),
                note=word["note"] if word["note"] is not None else definition.get("note", ""),
            )
        )
    for study in connection.execute(sa.select(t["study_sessions"])).mappings().all():
        rows = connection.execute(
            sa.select(t["study_answers"])
            .where(t["study_answers"].c.session_id == study["id"])
            .order_by(t["study_answers"].c.position)
        ).mappings()
        answers = [
            {"id": a["word_id"], "index": a["position"], "correct": a["correct"], **a["snapshot"]}
            for a in rows
        ]
        data = {
            "ids": study["data"]["ids"],
            "mode": study["mode"],
            "scope": study["scope"],
            "quizType": study["skill"],
            "index": study["position"],
            "correct": study["correct"],
            "answers": answers,
            "revealed": study["revealed"],
            "choice": study["choice"],
            "options": study["options"],
        }
        connection.execute(
            t["study_sessions"]
            .update()
            .where(t["study_sessions"].c.id == study["id"])
            .values(data=data)
        )
    op.drop_table("study_answers")
    op.drop_table("word_progress")
    with op.batch_alter_table("study_sessions") as batch:
        batch.drop_index("ix_sessions_resume")
        batch.drop_constraint("ck_session_counts", type_="check")
        batch.drop_constraint("ck_session_status", type_="check")
        for name in (
            "mode",
            "scope",
            "skill",
            "status",
            "position",
            "total",
            "correct",
            "revealed",
            "choice",
            "options",
        ):
            batch.drop_column(name)
    with op.batch_alter_table("words") as batch:
        batch.drop_index("ix_words_user_created")
        batch.drop_index("ix_words_vocabulary_id")
        batch.drop_constraint("fk_words_vocabulary", type_="foreignkey")
        batch.drop_column("vocabulary_id")
        batch.drop_column("search_text")
        batch.alter_column("marked_for_review", new_column_name="wrong", existing_type=sa.Boolean())
        batch.alter_column("meaning", nullable=False, existing_type=sa.String(300))
        batch.alter_column("note", nullable=False, existing_type=sa.String(600))
    op.drop_table("vocabulary")
