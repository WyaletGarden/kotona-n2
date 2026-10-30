from datetime import timezone
from sqlalchemy import func, select
from .catalogue import catalogue_info
from .constants import MASTERED_STREAK, public_limits
from .models import StudyAnswer, StudySession, now
from .repositories import owned_word, statistics
from .schemas import MutationOut, SessionOut, SkillProgress, WordOut, WorkspaceOut


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def word_out(word, skill="reading") -> WordOut:
    progress = {p.skill: SkillProgress.model_validate(p) for p in word.progress}
    for name in ("reading", "meaning"):
        progress.setdefault(name, SkillProgress())
    target = progress[skill]
    due = target.last_correct is False or (
        target.next_review_at is not None and aware(target.next_review_at) <= now()
    )
    return WordOut(
        id=word.id,
        kanji=word.kanji,
        reading=word.reading,
        meaning=word.meaning,
        note=word.note,
        marked_for_review=word.marked_for_review,
        seen=word.seen,
        correct=word.correct,
        known=all(p.streak >= MASTERED_STREAK for p in progress.values()),
        needs_review=word.marked_for_review or due,
        progress=progress,
    )


def session_out(db, user):
    study = db.get(StudySession, user.active_session_id) if user.active_session_id else None
    if not study:
        return None
    count = db.scalar(
        select(func.count()).select_from(StudyAnswer).where(StudyAnswer.session_id == study.id)
    )
    answer = db.get(StudyAnswer, (study.id, study.position))
    current = None
    if study.position < study.total and study.status in ("in_progress", "paused"):
        current = word_out(owned_word(db, user, study.data["ids"][study.position]), study.skill)
    return SessionOut(
        id=study.id,
        mode=study.mode,
        scope=study.scope,
        quizType=study.skill,
        status=study.status,
        index=study.position,
        total=study.total,
        correct=study.correct,
        answered_count=count,
        answered=answer is not None,
        current_result=answer.correct if answer else None,
        revealed=study.revealed,
        choice=study.choice,
        options=study.options,
        current_word=current,
    )


def snapshot(db, user):
    db.flush()
    return dict(
        revision=user.revision,
        view=user.view,
        settings=user.settings,
        stats=statistics(db, user),
        session=session_out(db, user),
    )


def workspace(db, user):
    return WorkspaceOut(**snapshot(db, user), limits=public_limits(), catalogue=catalogue_info())


def mutation(db, user, *, updated=(), deleted=(), imported=0, duplicates=0):
    return MutationOut(
        **snapshot(db, user),
        updated_words=[word_out(w, user.settings["quizType"]) for w in updated],
        deleted_ids=list(deleted),
        imported=imported,
        duplicates=duplicates,
    )
