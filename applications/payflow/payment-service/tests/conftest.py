import pytest
from fastapi.testclient import TestClient
from app import routes
from app.main import app
from app.service import PaymentStore


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "store", PaymentStore())
    with TestClient(app) as client:
        yield client
