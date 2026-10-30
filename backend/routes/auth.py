from fastapi import APIRouter, Request, Response
from ..db import Db
from ..schemas import Credentials, Identity, Register
from ..security import COOKIE, CurrentUser, set_cookie
from ..services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=Identity)
def register(payload: Register, request: Request, response: Response, db: Db):
    auth.throttle(db, request.client.host if request.client else "unknown")
    user = auth.register(db, payload)
    token, identity = auth.create_login(db, user)
    set_cookie(response, token)
    return identity


@router.post("/login", response_model=Identity)
def login(payload: Credentials, request: Request, response: Response, db: Db):
    auth.throttle(db, request.client.host if request.client else "unknown")
    token, identity = auth.create_login(db, auth.login(db, payload))
    set_cookie(response, token)
    return identity


@router.get("/me", response_model=Identity)
def me(request: Request, user: CurrentUser):
    return {"user": user, "csrf": request.state.login.csrf}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, user: CurrentUser, db: Db):
    db.delete(request.state.login)
    response.delete_cookie(COOKIE, path="/")
