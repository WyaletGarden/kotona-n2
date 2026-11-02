from datetime import timezone
from .catalogue import catalogue_info
from .constants import MASTERED_STREAK, public_limits
from .models import now
from .repositories import answer_summary, owned_session, owned_word, statistics
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


def session_out(db, user, *, study=None, summary=None):
    study = study or (
        owned_session(db, user, user.active_session_id, required=False)
        if user.active_session_id
        else None
    )
    if not study:
        return None
    count, result = summary if summary is not None else answer_summary(db, study)
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
        answered=result is not None,
        current_result=result,
        revealed=study.revealed,
        choice=study.choice,
        options=study.options,
        current_word=current,
    )


def snapshot(db, user, *, study=None, summary=None):
    db.flush()
    stats = statistics(db, user)
    stats["valid_until"] = aware(stats["valid_until"])
    # A relative deadline avoids refresh loops when the browser clock differs
    # from the server clock. The next workspace read recomputes time-based counts.
    stats["refresh_after_ms"] = (
        max(0, int((stats["valid_until"] - now()).total_seconds() * 1000))
        if stats["valid_until"]
        else None
    )
    return dict(
        revision=user.revision,
        view=user.view,
        settings=user.settings,
        stats=stats,
        session=session_out(db, user, study=study, summary=summary),
    )


def workspace(db, user):
    return WorkspaceOut(**snapshot(db, user), limits=public_limits(), catalogue=catalogue_info())


def mutation(
    db, user, *, updated=(), deleted=(), imported=0, duplicates=0, study=None, summary=None
):
    return MutationOut(
        **snapshot(db, user, study=study, summary=summary),
        updated_words=[word_out(w, user.settings["quizType"]) for w in updated],
        deleted_ids=list(deleted),
        imported=imported,
        duplicates=duplicates,
    )
