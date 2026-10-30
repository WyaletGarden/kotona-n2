"""HTTP authentication dependencies; business services do not depend on FastAPI."""

import hashlib
import secrets
from typing import Annotated
from fastapi import Depends, Request, Response
from pwdlib import PasswordHash
from sqlalchemy import select
from .config import settings
from .db import Db
from .errors import DomainError, conflict
from .models import LoginSession, User, now
from .presenters import aware

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("timing-equalization-password")
COOKIE = "kotoba_session"


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def set_cookie(response: Response, token: str):
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="lax",
        max_age=settings().session_days * 86400,
        path="/",
    )


def authenticated(request: Request, db: Db) -> User:
    token = request.cookies.get(COOKIE)
    login = db.get(LoginSession, digest(token)) if token else None
    if not login or aware(login.expires_at) <= now():
        raise DomainError(401, "unauthenticated", "Vui lòng đăng nhập lại.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), login.csrf):
            raise DomainError(403, "csrf_failed", "Phiên xác thực không hợp lệ. Hãy tải lại trang.")
    request.state.login = login
    user = db.get(User, login.user_id)
    if not user:
        raise DomainError(401, "unauthenticated", "Vui lòng đăng nhập lại.")
    return user


CurrentUser = Annotated[User, Depends(authenticated, scope="function")]


def writable(request: Request, user: CurrentUser, db: Db) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if request.headers.get("X-Revision") != str(user.revision):
        conflict(
            "revision_conflict",
            "Dữ liệu đã thay đổi ở phiên khác. Hãy thực hiện lại trên dữ liệu mới.",
        )
    user.revision += 1
    return user


WritableUser = Annotated[User, Depends(writable, scope="function")]
