"""Shared fixtures: a scripted fake model (PDF section 10) and an app on a temporary database."""
from __future__ import annotations

import itertools
import sqlite3
from types import SimpleNamespace
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

STAFF_EMAIL = "staff@example.com"
STAFF_PASSWORD = "test-staff-password"
_ids = itertools.count(1)


def text(reply: str) -> SimpleNamespace:
    """A final model response with one text block."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=reply)],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


def tool_call(name: str, tool_input: dict[str, Any]) -> SimpleNamespace:
    """A model response that requests one tool."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", id=f"toolu_{next(_ids)}", name=name, input=tool_input)],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


class FakeModel:
    """Replays a script of responses. A callable entry receives the request and returns a response."""

    def __init__(self, script: list[Any] | None = None, default: Any = None):
        self.script = list(script or [])
        self.default = default
        self.calls: list[dict[str, Any]] = []

    def complete(self, **request: Any) -> Any:
        self.calls.append(request)
        step: Any = self.script.pop(0) if self.script else self.default
        if step is None:
            raise AssertionError("FakeModel ran out of scripted responses")
        return step(request) if callable(step) else step


@pytest.fixture
def fake_model() -> FakeModel:
    return FakeModel()


@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
def client(fake_model: FakeModel, db_path: str):
    app = create_app(project_name="rental-demo", database_path=db_path, model=fake_model, staff_password=STAFF_PASSWORD)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def staff_client(client: TestClient) -> TestClient:
    response = client.post("/api/login", json={"email": STAFF_EMAIL, "password": STAFF_PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["state"]["role"] == "back_office"
    return client


@pytest.fixture
def db(db_path: str, client: TestClient) -> Callable[..., list[sqlite3.Row]]:
    """Run a read query against the test database."""

    def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    return query
