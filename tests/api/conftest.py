from datetime import date

import pytest
from fastapi.testclient import TestClient

from catalog.api.app import create_app

KEY = "test-key-not-a-secret"


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(create_app(KEY, today=lambda: date(2026, 10, 30)))


@pytest.fixture(scope="session")
def headers() -> dict[str, str]:
    return {"X-API-Key": KEY}
