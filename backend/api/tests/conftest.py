import pytest
from fastapi.testclient import TestClient
from app.api.routers import incidents as routes
from app.main import app
from app.services.incidents import IncidentStore
from app.api.dependencies import current_user


@pytest.fixture
def client(monkeypatch):
    new_store = IncidentStore()
    monkeypatch.setattr(routes, "store", new_store)
    from app import routes as root_routes
    monkeypatch.setattr(root_routes, "store", new_store)
    app.dependency_overrides[current_user] = lambda: "test-operator"
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(current_user, None)
