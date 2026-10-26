"""Health endpoint tests."""

import subprocess
import sys
from pathlib import Path


def test_health_returns_success(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": "Python AI service is running",
    }


def test_health_does_not_load_ai_libraries() -> None:
    """Importing the app for the health check must not load later AI packages."""
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.main, sys; "
            "assert 'sentence_transformers' not in sys.modules; "
            "assert 'chromadb' not in sys.modules",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
