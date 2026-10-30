import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from .api import router
from .db import engine
from .errors import DomainError
from .middleware import BodyTooLarge, SecurityMiddleware

app = FastAPI(
    title="Kotoba API",
    version="2.0.0",
    description="Sổ từ JLPT N2 và tiến độ học theo từng kỹ năng.",
)
app.add_middleware(SecurityMiddleware)


@app.exception_handler(BodyTooLarge)
async def body_limit(request: Request, exc: BodyTooLarge):
    return JSONResponse({"detail": exc.detail, "code": "body_too_large"}, status_code=413)


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    headers = {"Retry-After": "900"} if exc.code == "rate_limited" else None
    return JSONResponse(
        {"detail": exc.message, "code": exc.code}, status_code=exc.status, headers=headers
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logging.getLogger("kotoba").exception("Database request failed", exc_info=exc)
    return JSONResponse(
        {
            "detail": "Không thể truy cập cơ sở dữ liệu. Vui lòng thử lại.",
            "code": "database_unavailable",
        },
        status_code=503,
    )


@app.get("/api/health", tags=["operations"])
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


app.include_router(router)
app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parents[1] / "dist", html=True),
    name="frontend",
)
