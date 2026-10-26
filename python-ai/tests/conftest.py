"""Shared test fixtures.

Tests use FastAPI's in-process client, so they do not need a running server
or any AI model.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
