import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.db import Base, get_db
from backend.main import app


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    schema = "test_" + uuid4().hex
    if url:
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory.begin() as db:
            yield db

    app.dependency_overrides[get_db] = override
    import backend.main

    monkeypatch.setattr(backend.main, "engine", engine)
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()
    if url:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


class Account:
    def __init__(self, client, email="learner@example.com"):
        self.client = client
        self.email = email
        response = client.post(
            "/api/auth/register",
            json={"name": "Học viên", "email": email, "password": "strong-password-123"},
        )
        assert response.status_code == 201, response.text
        self.csrf = response.json()["csrf"]
        self.state = client.get("/api/workspace").json()

    def reload(self):
        self.state = self.client.get("/api/workspace").json()
        return self.state

    def write(self, method, path, body=None, revision=None):
        response = self.client.request(
            method,
            "/api" + path,
            json=body,
            headers={
                "X-CSRF-Token": self.csrf,
                "X-Revision": str(self.state["revision"] if revision is None else revision),
            },
        )
        if response.is_success and response.content and "revision" in response.json():
            self.state.update(response.json())
        return response

    def page(self, **params):
        return self.client.get("/api/words", params=params).json()

    def start(self, **options):
        response = self.write(
            "POST",
            "/study/sessions",
            {
                "mode": "flash",
                "scope": "all",
                "count": 10,
                "quizType": "reading",
                "view": "flash",
                **options,
            },
        )
        assert response.status_code == 201, response.text
        return self.state["session"]

    def action(self, action, **values):
        session = self.state["session"]
        return self.write(
            "POST",
            "/study/actions",
            {
                "session_id": session["id"],
                "index": session["index"],
                "action": action,
                **values,
            },
        )

    def flash(self, correct=True):
        assert self.action("reveal").status_code == 200
        response = self.action("flash_answer", correct=correct)
        assert response.status_code == 200, response.text
        return response


@pytest.fixture
def client(database):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def account(client):
    return Account(client)
