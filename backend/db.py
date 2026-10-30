from typing import Annotated
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    # Function scope commits/rolls back BEFORE FastAPI sends a successful response.
    # Services and presenters may flush but never commit the request transaction.
    with SessionLocal.begin() as db:
        yield db


Db = Annotated[Session, Depends(get_db, scope="function")]
