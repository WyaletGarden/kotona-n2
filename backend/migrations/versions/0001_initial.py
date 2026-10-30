"""Initial accounts, personal vocabulary and study history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    json = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("view", sa.String(16), nullable=False),
        sa.Column("settings", json, nullable=False),
        sa.Column("active_session_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "login_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("csrf", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])
    op.create_index("ix_login_sessions_expires_at", "login_sessions", ["expires_at"])
    op.create_table(
        "auth_attempts",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer, nullable=False),
        sa.Column("window", sa.Integer, nullable=False),
    )
    op.create_table(
        "words",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kanji", sa.String(80), nullable=False),
        sa.Column("reading", sa.String(120), nullable=False),
        sa.Column("meaning", sa.String(300), nullable=False),
        sa.Column("note", sa.String(600), nullable=False),
        sa.Column("wrong", sa.Boolean, nullable=False),
        sa.Column("seen", sa.Integer, nullable=False),
        sa.Column("correct", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "kanji", "reading", name="uq_user_word_reading"),
        sa.CheckConstraint("seen >= 0 AND correct >= 0 AND correct <= seen", name="ck_word_counts"),
    )
    op.create_index("ix_words_user_id", "words", ["user_id"])
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("data", json, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_study_sessions_user_id", "study_sessions", ["user_id"])


def downgrade():
    for table in ("study_sessions", "words", "auth_attempts", "login_sessions", "users"):
        op.drop_table(table)
