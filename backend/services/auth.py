import secrets
import time
from datetime import timedelta
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..config import settings
from ..errors import DomainError
from ..models import AuthAttempt, LoginSession, User, now
from ..security import DUMMY_HASH, digest, password_hash
from ..seed import populate_user


def throttle(db, client_ip: str):
    # Independent transaction: failed authentication must still consume an attempt.
    with Session(db.get_bind()) as attempts, attempts.begin():
        key = digest(client_ip)
        if attempts.get_bind().dialect.name == "postgresql":
            attempts.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(key[:15], 16)})
        row = attempts.get(AuthAttempt, key)
        window = int(time.time()) // 900
        if not row:
            row = AuthAttempt(key=key, count=0, window=window)
            attempts.add(row)
        if row.window != window:
            row.count, row.window = 0, window
        if row.count >= settings().auth_limit:
            raise DomainError(
                429, "rate_limited", "Quá nhiều lần thử. Vui lòng thử lại sau 15 phút."
            )
        row.count += 1


def register(db, payload):
    user = User(
        email=str(payload.email).lower(),
        name=payload.name,
        password_hash=password_hash.hash(payload.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        raise DomainError(409, "duplicate_email", "Email này đã được đăng ký.")
    populate_user(db, user, apply=True, bump_revision=False)
    return user


def login(db, payload):
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    valid = password_hash.verify(payload.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise DomainError(401, "invalid_credentials", "Email hoặc mật khẩu không đúng.")
    return user


def create_login(db, user):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute(delete(LoginSession).where(LoginSession.expires_at < now()))
    db.add(
        LoginSession(
            token_hash=digest(token),
            user_id=user.id,
            csrf=csrf,
            expires_at=now() + timedelta(days=settings().session_days),
        )
    )
    db.flush()
    return token, {"user": {"id": user.id, "name": user.name, "email": user.email}, "csrf": csrf}
