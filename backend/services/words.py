from sqlalchemy import func, select
from ..constants import MAX_WORDS
from ..errors import DomainError, conflict
from ..models import StudySession, Vocabulary, Word
from ..normalization import search_text
from ..repositories import owned_word
from ..schemas import WordInput


def capacity(db, user, adding=1):
    count = db.scalar(select(func.count()).select_from(Word).where(Word.user_id == user.id))
    if count + adding > MAX_WORDS:
        raise DomainError(422, "capacity_exceeded", "Sổ từ đã đạt giới hạn cho phép.")
    return MAX_WORDS - count


def ensure_unique(db, user, payload, exclude=None):
    duplicate = db.scalar(
        select(Word.id).where(
            Word.user_id == user.id,
            Word.kanji == payload.kanji,
            Word.reading == payload.reading,
            Word.id != (exclude or ""),
        )
    )
    if duplicate:
        conflict("duplicate_word", "Từ và cách đọc này đã có trong sổ từ.")


def make_word(user_id: str, payload: WordInput, shared: Vocabulary | None = None):
    return Word(
        user_id=user_id,
        vocabulary=shared,
        kanji=payload.kanji,
        reading=payload.reading,
        meaning_override=None if shared and payload.meaning == shared.meaning else payload.meaning,
        note_override=None if shared and payload.note == shared.note else payload.note,
        search_text=search_text(payload.kanji, payload.reading, payload.meaning),
    )


def add_word(db, user, payload):
    capacity(db, user)
    ensure_unique(db, user, payload)
    shared = db.scalar(
        select(Vocabulary).where(
            Vocabulary.kanji == payload.kanji, Vocabulary.reading == payload.reading
        )
    )
    word = make_word(user.id, payload, shared)
    db.add(word)
    db.flush()
    return word


def invalidate_sessions(db, user, word_id, *, skill=None):
    sessions = db.scalars(
        select(StudySession).where(
            StudySession.user_id == user.id,
            StudySession.status.in_(["in_progress", "paused"]),
        )
    )
    for study in sessions:
        if word_id in study.data["ids"] and (skill is None or study.skill == skill):
            study.status = "invalidated"
            if user.active_session_id == study.id:
                user.active_session_id = None


def update_word(db, user, word_id, payload):
    word = owned_word(db, user, word_id)
    ensure_unique(db, user, payload, word_id)
    identity_changed = (word.kanji, word.reading) != (payload.kanji, payload.reading)
    meaning_changed = word.meaning != payload.meaning
    if identity_changed or meaning_changed:
        skill = None if identity_changed else "meaning"
        invalidate_sessions(db, user, word.id, skill=skill)
        for progress in list(word.progress):
            if skill is None or progress.skill == skill:
                word.progress.remove(progress)
        # A changed word cannot inherit mastery from its former identity.
        word.seen = sum(p.seen for p in word.progress)
        word.correct = sum(p.correct for p in word.progress)
        if identity_changed:
            word.marked_for_review = False
    shared = db.scalar(
        select(Vocabulary).where(
            Vocabulary.kanji == payload.kanji, Vocabulary.reading == payload.reading
        )
    )
    word.vocabulary = shared
    word.kanji, word.reading = payload.kanji, payload.reading
    word.meaning_override = (
        None if shared and payload.meaning == shared.meaning else payload.meaning
    )
    word.note_override = None if shared and payload.note == shared.note else payload.note
    word.search_text = search_text(payload.kanji, payload.reading, payload.meaning)
    db.flush()
    return word


def delete_word(db, user, word_id):
    word = owned_word(db, user, word_id)
    invalidate_sessions(db, user, word.id)
    db.delete(word)
    db.flush()


def plan_import(db, user, words):
    keys = set(db.execute(select(Word.kanji, Word.reading).where(Word.user_id == user.id)).tuples())
    remaining = MAX_WORDS - len(keys)
    adding = []
    for word in words:
        key = (word.kanji, word.reading)
        if key not in keys:
            keys.add(key)
            adding.append(word)
    if len(adding) > remaining:
        raise DomainError(422, "capacity_exceeded", f"Chỉ còn {remaining} chỗ trống trong sổ từ.")
    return adding, len(words) - len(adding), remaining


def import_words(db, user, words):
    adding, duplicates, _ = plan_import(db, user, words)
    shared = {(v.kanji, v.reading): v for v in db.scalars(select(Vocabulary))}
    db.add_all(make_word(user.id, w, shared.get((w.kanji, w.reading))) for w in adding)
    db.flush()
    return len(adding), duplicates
