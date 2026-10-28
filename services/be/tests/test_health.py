"""Kiểm tra hai endpoint vận hành: `/health` và `/api/version`.

Gắn router vào một app trống thay vì import `be.main`, vì ứng dụng thật mở một
Redis pool khi startup, còn test này phải chạy được khi không có hạ tầng nào
đang bật.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from be.config import Settings, get_settings
from be.routes import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_reports_ok() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.fixture
def fresh_settings(monkeypatch):
    # Không đọc `.env` thật của máy: một máy điền AIAFA_VERSION ở đó thì ca *không đặt* đỏ oan.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_version_reports_the_lab_tag(monkeypatch, fresh_settings) -> None:
    monkeypatch.setenv("AIAFA_VERSION", "lab-2026.0.1")
    response = _client().get("/api/version")
    assert response.status_code == 200
    assert response.json() == {"version": "lab-2026.0.1"}


@pytest.mark.parametrize("value", [None, "", "  "])
def test_version_without_a_tag_says_so(monkeypatch, fresh_settings, value) -> None:
    """Không đặt, hay để trống như `.env.example`: không có tên, không phải tên rỗng."""
    if value is None:
        monkeypatch.delenv("AIAFA_VERSION", raising=False)
    else:
        monkeypatch.setenv("AIAFA_VERSION", value)
    assert _client().get("/api/version").json() == {"version": "chưa có phiên bản"}
