import pytest
from fastapi.testclient import TestClient
from app import routes
from app.main import app
from app.service import PaymentStore
from app.api.dependencies import current_user


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "store", PaymentStore())
    app.dependency_overrides[current_user] = lambda: "test-operator"
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(current_user, None)
