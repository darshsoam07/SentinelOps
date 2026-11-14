import pytest
from fastapi.testclient import TestClient
from app import routes
from app.main import app
from app.service import IncidentStore


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "store", IncidentStore())
    with TestClient(app) as client:
        yield client
