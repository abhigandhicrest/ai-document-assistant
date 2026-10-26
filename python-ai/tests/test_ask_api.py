"""Question API tests.

Embeddings and the language model are replaced so these tests stay local.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_embedder, get_llm
from app.main import app
from tests.fakes import FakeLlm, KeywordEmbedder
from tests.pdf_factory import make_pdf


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    laravel_dir = tmp_path / "laravel-private"
    laravel_dir.mkdir()
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("METADATA_DB_PATH", str(tmp_path / "documents.db"))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("LARAVEL_STORAGE_DIR", str(laravel_dir))
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("API_TOKEN", "")
    get_settings.cache_clear()
    llm = FakeLlm("The total is 42.")
    app.dependency_overrides[get_embedder] = lambda: KeywordEmbedder()
    app.dependency_overrides[get_llm] = lambda: llm
    yield {"upload_dir": upload_dir, "laravel_dir": laravel_dir, "llm": llm}
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def client(isolated) -> TestClient:
    return TestClient(app)


def test_laravel_ask_indexes_the_private_pdf_and_returns_an_answer(client, isolated) -> None:
    pdf_path = isolated["laravel_dir"] / "documents" / "1"
    pdf_path.mkdir(parents=True)
    (pdf_path / "contract.pdf").write_bytes(make_pdf(["alpha contract total 42"]))

    response = client.post(
        "/ask",
        json={
            "document_id": 1,
            "user_id": 1,
            "filename": "contract.pdf",
            "storage_path": "documents/1/contract.pdf",
            "question": "What is the alpha total?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "The total is 42."
    assert body["meta"]["retrieved_chunk_count"] == 1
    assert body["meta"]["sources"][0]["page_numbers"] == [1]
    assert "alpha contract total 42" in body["meta"]["sources"][0]["excerpt"]
    assert "storage" not in response.text
    assert isolated["llm"].prompts


def test_laravel_ask_rejects_a_path_outside_private_storage(client, isolated) -> None:
    outside = isolated["laravel_dir"].parent / "secret.pdf"
    outside.write_bytes(make_pdf(["alpha secret"]))

    response = client.post(
        "/ask",
        json={
            "document_id": 1,
            "user_id": 1,
            "filename": "secret.pdf",
            "storage_path": "../secret.pdf",
            "question": "What is the alpha total?",
        },
    )

    assert response.status_code == 400
    assert response.json()["message"] == "The document path is not valid."
    assert outside.is_file()


def test_chat_requires_a_processed_document(client) -> None:
    uploaded = client.post(
        "/api/documents/upload",
        files={"file": ("notes.pdf", make_pdf(["alpha contract total 42"]), "application/pdf")},
    )
    document_id = uploaded.json()["document_id"]

    early = client.post("/api/chat/ask", json={"question": "What is the alpha total?", "document_id": document_id})
    assert early.status_code == 409

    processed = client.post(f"/api/documents/{document_id}/process")
    assert processed.status_code == 200
    assert processed.json()["status"] == "processed"
    assert processed.json()["chunk_count"] >= 1

    answer = client.post("/api/chat/ask", json={"question": "What is the alpha total?", "document_id": document_id})
    assert answer.status_code == 200
    assert answer.json()["answer"] == "The total is 42."
    assert answer.json()["sources"][0]["document_id"] == document_id


def test_chat_rejects_an_empty_question_and_a_large_top_k(client) -> None:
    assert client.post("/api/chat/ask", json={"question": "   "}).status_code == 422
    assert client.post("/api/chat/ask", json={"question": "What is the total?", "top_k": 0}).status_code == 422
    assert client.post("/api/chat/ask", json={"question": "What is the total?", "top_k": 11}).status_code == 422


def test_missing_document_returns_404(client) -> None:
    response = client.get("/api/documents/missing-document")

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_delete_removes_the_file_and_the_record(client, isolated) -> None:
    uploaded = client.post(
        "/api/documents/upload",
        files={"file": ("notes.pdf", make_pdf(["alpha contract"]), "application/pdf")},
    )
    document_id = uploaded.json()["document_id"]
    assert client.post(f"/api/documents/{document_id}/process").status_code == 200

    deleted = client.delete(f"/api/documents/{document_id}")

    assert deleted.status_code == 200
    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert list(isolated["upload_dir"].glob("*.pdf")) == []


def test_blank_pdf_is_marked_failed(client) -> None:
    uploaded = client.post(
        "/api/documents/upload",
        files={"file": ("blank.pdf", make_pdf([""]), "application/pdf")},
    )
    document_id = uploaded.json()["document_id"]

    response = client.post(f"/api/documents/{document_id}/process")

    assert response.status_code == 422
    details = client.get(f"/api/documents/{document_id}").json()
    assert details["status"] == "failed"
    assert "no extractable text" in details["error_message"]


def test_api_token_protects_questions_but_not_health(client, isolated, monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "local-secret")
    get_settings.cache_clear()

    assert client.get("/api/health").status_code == 200
    denied = client.post("/api/chat/ask", json={"question": "What is the total?"})
    assert denied.status_code == 401

    allowed = client.post(
        "/api/chat/ask",
        json={"question": "What is the total?"},
        headers={"Authorization": "Bearer local-secret"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["answer"]
