"""Reusable SQL queries; ownership and pagination stay in the database."""

from sqlalchemy import Integer, and_, case, cast, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload
from .constants import MASTERED_STREAK
from .errors import DomainError
from .models import StudyAnswer, StudySession, User, Vocabulary, Word, WordProgress, now
from .normalization import normalize_text


def mastered():
    return and_(
        *[
            exists(
                select(WordProgress.word_id).where(
                    WordProgress.word_id == Word.id,
                    WordProgress.skill == skill,
                    WordProgress.streak >= MASTERED_STREAK,
                )
            )
            for skill in ("reading", "meaning")
        ]
    )


def review_due(skill: str):
    return or_(
        Word.marked_for_review,
        exists(
            select(WordProgress.word_id).where(
                WordProgress.word_id == Word.id,
                WordProgress.skill == skill,
                or_(WordProgress.last_correct.is_(False), WordProgress.next_review_at <= now()),
            )
        ),
    )


def word_query(user: User, *, q="", status="all"):
    statement = select(Word).where(Word.user_id == user.id)
    if q.strip():
        statement = statement.where(
            Word.search_text.contains(normalize_text(q.strip()), autoescape=True)
        )
    if status == "review":
        statement = statement.where(review_due(user.settings["quizType"]))
    elif status == "known":
        statement = statement.where(mastered())
    elif status == "new":
        statement = statement.where(Word.seen == 0)
    elif status == "learning":
        statement = statement.where(Word.seen > 0, ~mastered())
    return statement


def owned_word(db: Session, user: User, word_id: str) -> Word:
    cache = db.info.setdefault("owned_words", {})
    key = (user.id, word_id)
    if key in cache:
        return cache[key]
    # One word has at most two progress rows. Join them on single-word reads;
    # paginated lists retain selectin loading to avoid multiplying page rows.
    word = (
        db.execute(
            select(Word)
            .where(Word.id == word_id, Word.user_id == user.id)
            .options(joinedload(Word.progress))
        )
        .unique()
        .scalar_one_or_none()
    )
    if not word:
        raise DomainError(404, "word_not_found", "Không tìm thấy từ vựng.")
    cache[key] = word
    return word


def owned_session(
    db: Session, user: User, session_id: str, *, required=True
) -> StudySession | None:
    cache = db.info.setdefault("owned_sessions", {})
    key = (user.id, session_id)
    if key in cache:
        return cache[key]
    study = db.scalar(
        select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user.id)
    )
    if not study:
        if not required:
            return None
        raise DomainError(404, "session_not_found", "Không tìm thấy phiên học.")
    cache[key] = study
    return study


def answer_summary(db: Session, study: StudySession):
    count, result = db.execute(
        select(
            func.count(StudyAnswer.position),
            func.max(
                case(
                    (StudyAnswer.position == study.position, cast(StudyAnswer.correct, Integer)),
                    else_=None,
                )
            ),
        ).where(StudyAnswer.session_id == study.id)
    ).one()
    return count, bool(result) if result is not None else None


def statistics(db: Session, user: User):
    cutoff = now()
    next_due = (
        select(func.min(WordProgress.next_review_at))
        .join(Word, Word.id == WordProgress.word_id)
        .where(
            Word.user_id == user.id,
            Word.marked_for_review.is_(False),
            WordProgress.skill == user.settings["quizType"],
            WordProgress.last_correct.is_not(False),
            WordProgress.next_review_at > cutoff,
        )
        .scalar_subquery()
    )
    return dict(
        db.execute(
            select(
                func.count(Word.id).label("total"),
                func.coalesce(func.sum(case((mastered(), 1), else_=0)), 0).label("known"),
                func.coalesce(
                    func.sum(case((review_due(user.settings["quizType"]), 1), else_=0)), 0
                ).label("review"),
                func.coalesce(func.sum(case((Word.seen == 0, 1), else_=0)), 0).label("new"),
                next_due.label("valid_until"),
            ).where(Word.user_id == user.id)
        )
        .mappings()
        .one()
    )


def distractors(db: Session, user: User, skill: str, correct: str):
    value = (
        Word.reading
        if skill == "reading"
        else func.coalesce(Word.meaning_override, Vocabulary.meaning)
    )
    choices = (
        select(value.label("value"))
        .select_from(Word)
        .outerjoin(Vocabulary)
        .where(
            Word.user_id == user.id,
            value != correct,
        )
        .distinct()
        .subquery()
    )
    return list(db.scalars(select(choices.c.value).order_by(func.random()).limit(3)))
