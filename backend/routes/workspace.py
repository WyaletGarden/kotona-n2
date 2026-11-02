from fastapi import APIRouter, Request
from ..catalogue import catalogue_info
from ..db import Db
from ..presenters import mutation, workspace
from ..schemas import BootstrapOut, CatalogueInfo, Identity, MutationOut, Preferences, WorkspaceOut
from ..errors import DomainError
from ..security import CurrentUser, WritableUser, authenticated

router = APIRouter(tags=["workspace"])


@router.get("/bootstrap", response_model=BootstrapOut)
def bootstrap(request: Request, db: Db):
    catalogue = catalogue_info()
    try:
        user = authenticated(request, db)
    except DomainError as exc:
        if exc.code != "unauthenticated":
            raise
        return BootstrapOut(catalogue=catalogue)
    return BootstrapOut(
        catalogue=catalogue,
        identity=Identity(user=user, csrf=request.state.login.csrf),
        workspace=workspace(db, user),
    )


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
