from fastapi import APIRouter
from ..catalogue import catalogue_info
from ..db import Db
from ..presenters import mutation, workspace
from ..schemas import CatalogueInfo, MutationOut, Preferences, WorkspaceOut
from ..security import CurrentUser, WritableUser

router = APIRouter(tags=["workspace"])


@router.get("/catalogue", response_model=CatalogueInfo)
def catalogue():
    return catalogue_info()


@router.get("/workspace", response_model=WorkspaceOut)
def load(user: CurrentUser, db: Db):
    return workspace(db, user)


@router.put("/preferences", response_model=MutationOut)
def preferences(payload: Preferences, user: WritableUser, db: Db):
    user.settings = {"count": payload.count, "quizType": payload.quizType}
    user.view = payload.view
    return mutation(db, user)
