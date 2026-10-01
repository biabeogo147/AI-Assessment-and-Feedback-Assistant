"""Kiểm tra health endpoint.

Gắn router vào một app trống thay vì import `be.main`, vì ứng dụng thật mở một
Redis pool khi startup, còn test này phải chạy được khi không có hạ tầng nào
đang bật.
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
