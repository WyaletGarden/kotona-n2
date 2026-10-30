from fastapi import APIRouter
from .routes import auth, study, words, workspace

router = APIRouter(prefix="/api")
for child in (auth.router, workspace.router, words.router, study.router):
    router.include_router(child)
