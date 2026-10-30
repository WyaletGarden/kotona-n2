import random
from datetime import timedelta

from sqlalchemy import select

from ..constants import REVIEW_DAYS
from ..errors import DomainError, conflict
from ..models import StudyAnswer, StudySession, Word, WordProgress, now
from ..repositories import distractors, owned_session, owned_word, word_query
from ..schemas import FlashAnswerAction, QuizAnswerAction

rng = random.SystemRandom()


def set_options(db, user, study):
    study.options = []
    if study.mode == "quiz" and study.position < study.total:
        word = owned_word(db, user, study.data["ids"][study.position])
        correct = getattr(word, study.skill)
        options = [correct, *distractors(db, user, study.skill, correct)]
        rng.shuffle(options)
        study.options = options


def resume_session(db, user, session_id):
    study = owned_session(db, user, session_id)
    if study.status not in ("paused", "in_progress") or study.position >= study.total:
        conflict("session_not_resumable", "Phiên này không còn có thể tiếp tục.")
    if user.active_session_id and user.active_session_id != study.id:
        active = owned_session(db, user, user.active_session_id)
        if active.status == "in_progress":
            active.status = "paused"
    study.status = "in_progress"
    user.active_session_id = study.id
    user.view = "review" if study.scope == "wrong" else study.mode
    user.settings = {**user.settings, "quizType": study.skill}
    return study


def start_session(db, user, payload):
    active = owned_session(db, user, user.active_session_id) if user.active_session_id else None
    if active and active.status == "in_progress":
        active.status = "paused"
    if not payload.restart:
        candidate = db.scalar(
            select(StudySession)
            .where(
                StudySession.user_id == user.id,
                StudySession.status == "paused",
                StudySession.position < StudySession.total,
                StudySession.mode == payload.mode,
                StudySession.scope == payload.scope,
                StudySession.skill == payload.quizType,
            )
            .order_by(StudySession.created_at.desc())
            .limit(1)
        )
        if candidate:
            return resume_session(db, user, candidate.id)
    elif active and active.status == "paused":
        active.status = "abandoned"
    user.settings = {"count": payload.count, "quizType": payload.quizType}
    pool = list(
        db.scalars(
            word_query(user, status="review" if payload.scope == "wrong" else "all")
            .with_only_columns(Word.id)
            .order_by(None)
        )
    )
    ids = rng.sample(pool, min(payload.count or len(pool), len(pool)))
    study = StudySession(
        user_id=user.id,
        data={"ids": ids},
        mode=payload.mode,
        scope=payload.scope,
        skill=payload.quizType,
        total=len(ids),
        status="in_progress" if ids else "completed",
        completed_at=None if ids else now(),
    )
    db.add(study)
    db.flush()
    user.active_session_id, user.view = study.id, payload.view
    set_options(db, user, study)
    return study


def grade_progress(word, skill, correct):
    progress = next((p for p in word.progress if p.skill == skill), None)
    if progress is None:
        progress = WordProgress(skill=skill, seen=0, correct=0, streak=0)
        word.progress.append(progress)
    progress.seen += 1
    progress.correct += int(correct)
    progress.streak = progress.streak + 1 if correct else 0
    progress.last_correct = correct
    progress.next_review_at = now() + (
        timedelta(days=REVIEW_DAYS[min(progress.streak - 1, len(REVIEW_DAYS) - 1)])
        if correct
        else timedelta(minutes=10)
    )
    word.seen += 1
    word.correct += int(correct)


def act(db, user, payload):
    if not user.active_session_id or user.active_session_id != str(payload.session_id):
        conflict("session_conflict", "Phiên học đã thay đổi. Hãy tải lại dữ liệu.")
    study = owned_session(db, user, user.active_session_id)
    if (
        study.position != payload.index
        or study.status != "in_progress"
        or study.position >= study.total
    ):
        conflict("session_conflict", "Câu hỏi đã thay đổi hoặc phiên học đã kết thúc.")
    word = owned_word(db, user, study.data["ids"][study.position])
    answered = db.get(StudyAnswer, (study.id, study.position))
    if payload.action == "reveal":
        if study.mode != "flash":
            raise DomainError(422, "invalid_action", "Chỉ lật thẻ trong chế độ flashcard.")
        study.revealed = True
    elif isinstance(payload, (FlashAnswerAction, QuizAnswerAction)):
        if answered:
            conflict("already_answered", "Câu này đã được chấm điểm.")
        if isinstance(payload, FlashAnswerAction):
            if study.mode != "flash" or not study.revealed:
                raise DomainError(422, "invalid_action", "Hãy lật flashcard trước khi tự đánh giá.")
            correct = payload.correct
        else:
            if (
                study.mode != "quiz"
                or len(study.options) < 2
                or payload.choice not in study.options
            ):
                raise DomainError(422, "invalid_choice", "Lựa chọn không hợp lệ.")
            study.choice = payload.choice
            correct = payload.choice == getattr(word, study.skill)
        grade_progress(word, study.skill, correct)
        db.add(
            StudyAnswer(
                session_id=study.id,
                position=study.position,
                word_id=word.id,
                correct=correct,
                choice=study.choice,
                snapshot={"kanji": word.kanji, "reading": word.reading, "meaning": word.meaning},
            )
        )
        study.correct += int(correct)
        if study.mode == "flash":
            study.position += 1
            study.revealed = False
    elif payload.action == "next":
        if not answered:
            raise DomainError(422, "answer_required", "Hãy trả lời trước khi chuyển từ tiếp theo.")
        study.position += 1
        study.revealed, study.choice = False, None
        set_options(db, user, study)
    if study.position == study.total:
        study.status, study.completed_at = "completed", now()
    db.flush()
    return word
