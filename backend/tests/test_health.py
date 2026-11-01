from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app

client = TestClient(app)


class FakeSession:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def execute(self, _statement: object) -> None:
        if self.error:
            raise self.error


def get_health_with(session: FakeSession):
    app.dependency_overrides[get_db] = lambda: session
    try:
        return client.get("/health")
    finally:
        app.dependency_overrides.clear()


def test_health_returns_ok_when_database_responds() -> None:
    response = get_health_with(FakeSession())

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_returns_503_when_database_fails() -> None:
    error = OperationalError("SELECT 1", {}, Exception("connection refused"))

    response = get_health_with(FakeSession(error))

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
