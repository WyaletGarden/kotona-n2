from uuid import UUID
from fastapi import APIRouter, Query
from sqlalchemy import func, select
from ..constants import MAX_PAGE_SIZE
from ..db import Db
from ..models import StudyAnswer, StudySession
from ..presenters import mutation
from ..repositories import owned_session
from ..schemas import AnswerPage, HistoryPage, MutationOut, Start, StudyAction
from ..security import CurrentUser, WritableUser
from ..services import study

router = APIRouter(prefix="/study", tags=["study"])


@router.post("/sessions", status_code=201, response_model=MutationOut)
def start(payload: Start, user: WritableUser, db: Db):
    study.start_session(db, user, payload)
    return mutation(db, user)


@router.post("/sessions/{session_id}/resume", response_model=MutationOut)
def resume(session_id: UUID, user: WritableUser, db: Db):
    study.resume_session(db, user, str(session_id))
    return mutation(db, user)


@router.post("/actions", response_model=MutationOut)
def action(payload: StudyAction, user: WritableUser, db: Db):
    word = study.act(db, user, payload)
    return mutation(db, user, updated=[word])


@router.get("/history", response_model=HistoryPage)
def history(
    user: CurrentUser,
    db: Db,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    query = select(StudySession).where(StudySession.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(StudySession.created_at.desc(), StudySession.id).offset(offset).limit(limit)
    )
    sessions = list(rows)
    counts = (
        select(StudyAnswer.session_id, func.count())
        .where(StudyAnswer.session_id.in_([s.id for s in sessions]))
        .group_by(StudyAnswer.session_id)
    )
    answered = dict(db.execute(counts).tuples().all()) if sessions else {}
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": s.id,
                "mode": s.mode,
                "scope": s.scope,
                "quizType": s.skill,
                "status": s.status,
                "total": s.total,
                "correct": s.correct,
                "answered_count": answered.get(s.id, 0),
                "created_at": s.created_at,
                "completed_at": s.completed_at,
            }
            for s in sessions
        ],
    }


@router.get("/sessions/{session_id}/answers", response_model=AnswerPage)
def answers(
    session_id: UUID,
    user: CurrentUser,
    db: Db,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
):
    owned_session(db, user, str(session_id))
    query = select(StudyAnswer).where(StudyAnswer.session_id == str(session_id))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(StudyAnswer.position).offset(offset).limit(limit))
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "index": a.position,
                "correct": a.correct,
                "choice": a.choice,
                "answered_at": a.answered_at,
                **a.snapshot,
            }
            for a in rows
        ],
    }
