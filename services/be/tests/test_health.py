"""Health endpoint check.

Mounts the router on a bare app rather than importing `be.main`, because the
real application opens a Redis pool during startup and this test must pass
without any infrastructure running.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from be.routes import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_reports_ok() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
