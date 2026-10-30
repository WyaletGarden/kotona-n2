"""Disposable-schema HTTP server. DATABASE_URL is never an implicit test target."""

import os
from pathlib import Path
from uuid import uuid4
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config
import uvicorn


def main():
    url = os.environ.get("KOTOBA_E2E_DATABASE_URL")
    if not url:
        raise SystemExit("Set KOTOBA_E2E_DATABASE_URL to a disposable PostgreSQL database.")
    schema = "e2e_" + uuid4().hex
    Path(".runtime").mkdir(exist_ok=True)
    Path(".runtime/e2e-schema.txt").write_text(schema, encoding="utf-8")
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.connect() as connection:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        from backend.main import app
        import backend.main
        from backend.config import settings
        from backend.db import get_db

        factory = sessionmaker(engine, expire_on_commit=False)

        def override():
            with factory.begin() as db:
                yield db

        settings().app_origin = "http://127.0.0.1:8010"
        settings().cookie_secure = False
        settings().auth_limit = 1000
        app.dependency_overrides[get_db] = override
        backend.main.engine = engine

        @app.get("/api/test-environment")
        def test_environment():
            return {"isolated": True}

        route = app.router.routes.pop()
        app.router.routes.insert(0, route)
        uvicorn.run(app, host="127.0.0.1", port=8010, log_level="warning")
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


if __name__ == "__main__":
    main()
