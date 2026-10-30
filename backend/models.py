from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


json_type = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(512))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    view: Mapped[str] = mapped_column(String(16), default="flash")
    settings: Mapped[dict] = mapped_column(
        json_type, default=lambda: {"count": 10, "quizType": "reading"}
    )
    active_session_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    window: Mapped[int] = mapped_column(Integer)


class Vocabulary(Base):
    """Shared catalogue definitions. Personal edits live on Word, never here."""

    __tablename__ = "vocabulary"
    __table_args__ = (UniqueConstraint("kanji", "reading", name="uq_vocabulary_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kanji: Mapped[str] = mapped_column(String(80))
    reading: Mapped[str] = mapped_column(String(120))
    meaning: Mapped[str] = mapped_column(String(300))
    note: Mapped[str] = mapped_column(String(600))
    source_key: Mapped[str] = mapped_column(String(80))


class Word(Base):
    __tablename__ = "words"
    __table_args__ = (
        UniqueConstraint("user_id", "kanji", "reading", name="uq_user_word_reading"),
        CheckConstraint("seen >= 0 AND correct >= 0 AND correct <= seen", name="ck_word_counts"),
        Index("ix_words_user_created", "user_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    vocabulary_id: Mapped[str | None] = mapped_column(ForeignKey("vocabulary.id"), index=True)
    kanji: Mapped[str] = mapped_column(String(80))
    reading: Mapped[str] = mapped_column(String(120))
    meaning_override: Mapped[str | None] = mapped_column("meaning", String(300))
    note_override: Mapped[str | None] = mapped_column("note", String(600))
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    seen: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    search_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    vocabulary: Mapped[Vocabulary | None] = relationship(lazy="joined")
    progress: Mapped[list["WordProgress"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def meaning(self) -> str:
        if self.meaning_override is not None:
            return self.meaning_override
        return self.vocabulary.meaning if self.vocabulary else ""

    @meaning.setter
    def meaning(self, value: str):
        self.meaning_override = value

    @property
    def note(self) -> str:
        if self.note_override is not None:
            return self.note_override
        return self.vocabulary.note if self.vocabulary else ""

    @note.setter
    def note(self, value: str):
        self.note_override = value


class WordProgress(Base):
    __tablename__ = "word_progress"
    __table_args__ = (
        CheckConstraint(
            "seen >= 0 AND correct >= 0 AND correct <= seen AND streak >= 0",
            name="ck_progress_counts",
        ),
        CheckConstraint("skill IN ('reading', 'meaning')", name="ck_progress_skill"),
    )
    word_id: Mapped[str] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    skill: Mapped[str] = mapped_column(String(16), primary_key=True)
    seen: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_correct: Mapped[bool | None] = mapped_column(Boolean)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        CheckConstraint(
            "position >= 0 AND correct >= 0 AND correct <= total AND position <= total",
            name="ck_session_counts",
        ),
        CheckConstraint(
            "status IN ('in_progress','paused','completed','abandoned','invalidated')",
            name="ck_session_status",
        ),
        Index("ix_sessions_resume", "user_id", "status", "mode", "scope", "skill"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    data: Mapped[dict] = mapped_column(json_type)  # Fixed ID order; never rewritten per answer.
    mode: Mapped[str] = mapped_column(String(16), default="flash")
    scope: Mapped[str] = mapped_column(String(16), default="all")
    skill: Mapped[str] = mapped_column(String(16), default="reading")
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    position: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    revealed: Mapped[bool] = mapped_column(Boolean, default=False)
    choice: Mapped[str | None] = mapped_column(String(300))
    options: Mapped[list] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudyAnswer(Base):
    __tablename__ = "study_answers"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[str | None] = mapped_column(ForeignKey("words.id", ondelete="SET NULL"))
    correct: Mapped[bool] = mapped_column(Boolean)
    choice: Mapped[str | None] = mapped_column(String(300))
    snapshot: Mapped[dict] = mapped_column(json_type)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
