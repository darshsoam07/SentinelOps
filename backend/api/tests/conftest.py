import os

# Unit tests must never connect to a database inherited from the shell.
os.environ["SENTINELOPS_DATABASE_URL"] = ""

import pytest
from fastapi.testclient import TestClient
from app.api.routers import incidents as routes
from app.main import app
from app.services.incidents import IncidentStore


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "store", IncidentStore())
    from app.api.dependencies import current_user

    app.dependency_overrides[current_user] = lambda: "test-operator"
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(current_user)
