"""Upload route tests.

Each test gets its own upload folder and SQLite file, so nothing is written
under python-ai/storage.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.metadata_store import MetadataStore
from tests.pdf_factory import make_pdf


@pytest.fixture
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    database_path = tmp_path / "metadata" / "documents.db"
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("METADATA_DB_PATH", str(database_path))
    get_settings.cache_clear()
    yield {"upload_dir": upload_dir, "database_path": database_path}
    get_settings.cache_clear()


@pytest.fixture
def client(storage: dict[str, Path]) -> TestClient:
    return TestClient(app)


def test_uploads_a_pdf_under_a_generated_name(client: TestClient, storage: dict[str, Path]) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.pdf", make_pdf(["Sample contract total 42"]), "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["original_filename"] == "notes.pdf"
    assert body["status"] == "uploaded"
    assert body["message"] == "PDF uploaded. It has not been processed yet."
    assert "storage" not in response.text
    assert "stored_filename" not in body

    saved = list(storage["upload_dir"].iterdir())
    assert len(saved) == 1
    assert saved[0].name == f"{body['document_id']}.pdf"
    assert saved[0].name != "notes.pdf"

    record = MetadataStore(storage["database_path"]).get(body["document_id"])
    assert record is not None
    assert record.status == "uploaded"
    assert record.original_filename == "notes.pdf"
    assert record.stored_filename == saved[0].name
    assert record.page_count is None
    assert record.chunk_count is None


def test_uses_only_the_base_name_from_a_client_path(client: TestClient, storage: dict[str, Path]) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("..\\..\\secret.pdf", make_pdf(["Hello"]), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "secret.pdf"
    saved_names = [path.name for path in storage["upload_dir"].iterdir()]
    assert saved_names != ["secret.pdf"]
    assert not (storage["upload_dir"].parent / "secret.pdf").exists()


def test_rejects_a_non_pdf_extension(client: TestClient, storage: dict[str, Path]) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Only PDF files are accepted."
    assert list(storage["upload_dir"].iterdir()) == []


def test_rejects_an_empty_file(client: TestClient, storage: dict[str, Path]) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "The uploaded file is empty."
    assert list(storage["upload_dir"].iterdir()) == []


def test_rejects_an_invalid_pdf(client: TestClient, storage: dict[str, Path]) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("broken.pdf", b"%PDF-1.7\n%%EOF", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["status"] == "error"
    assert "valid PDF" in response.json()["message"]
    assert list(storage["upload_dir"].iterdir()) == []


def test_rejects_a_file_over_the_configured_size(
    client: TestClient,
    storage: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "0")
    get_settings.cache_clear()

    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.pdf", make_pdf(["Too big for a zero limit"]), "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["message"] == "The PDF is larger than the upload limit."
    assert list(storage["upload_dir"].iterdir()) == []
