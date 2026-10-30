from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Query
from sqlalchemy import func, select
from ..constants import MAX_PAGE_SIZE, PAGE_SIZE
from ..db import Db
from ..models import Vocabulary, Word
from ..presenters import mutation, word_out
from ..repositories import owned_word, word_query
from ..schemas import ImportPreview, ImportWords, MutationOut, Review, WordInput, WordPage
from ..security import CurrentUser, WritableUser
from ..services import words

router = APIRouter(prefix="/words", tags=["words"])


@router.get("", response_model=WordPage)
def page(
    user: CurrentUser,
    db: Db,
    q: str = Query("", max_length=300),
    status: Literal["all", "review", "known", "new", "learning"] = "all",
    offset: int = Query(0, ge=0),
    limit: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    query = word_query(user, q=q, status=status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Word.created_at, Word.id).offset(offset).limit(limit))
    return {
        "revision": user.revision,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [word_out(w, user.settings["quizType"]) for w in rows],
    }


@router.post("", status_code=201, response_model=MutationOut)
def add(payload: WordInput, user: WritableUser, db: Db):
    return mutation(db, user, updated=[words.add_word(db, user, payload)])


@router.post("/import/preview", response_model=ImportPreview)
def preview(payload: ImportWords, user: CurrentUser, db: Db):
    adding, duplicates, remaining = words.plan_import(db, user, payload.words)
    return {
        "added": len(adding),
        "duplicates": duplicates,
        "capacity_remaining": remaining,
        "samples": adding[:5],
    }


@router.post("/import", response_model=MutationOut)
def import_words(payload: ImportWords, user: WritableUser, db: Db):
    added, duplicates = words.import_words(db, user, payload.words)
    return mutation(db, user, imported=added, duplicates=duplicates)


@router.get("/export", response_model=list[WordInput])
def export(user: CurrentUser, db: Db):
    values = (
        select(
            Word.kanji,
            Word.reading,
            func.coalesce(Word.meaning_override, Vocabulary.meaning).label("meaning"),
            func.coalesce(Word.note_override, Vocabulary.note, "").label("note"),
        )
        .outerjoin(Vocabulary)
        .where(Word.user_id == user.id)
        .order_by(Word.created_at, Word.id)
    )
    return [WordInput(**row) for row in db.execute(values).mappings()]


@router.put("/{word_id}", response_model=MutationOut)
def update(word_id: UUID, payload: WordInput, user: WritableUser, db: Db):
    return mutation(db, user, updated=[words.update_word(db, user, str(word_id), payload)])


@router.patch("/{word_id}/review", response_model=MutationOut)
def review(word_id: UUID, payload: Review, user: WritableUser, db: Db):
    word = owned_word(db, user, str(word_id))
    word.marked_for_review = payload.marked_for_review
    return mutation(db, user, updated=[word])


@router.delete("/{word_id}", response_model=MutationOut)
def delete(word_id: UUID, user: WritableUser, db: Db):
    words.delete_word(db, user, str(word_id))
    return mutation(db, user, deleted=[word_id])
