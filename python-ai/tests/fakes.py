"""Stand-ins used by tests so they never download a model or call a provider."""

import httpx

from app.services.vector_store import RetrievedChunk
from app.utils.exceptions import AppError


class KeywordEmbedder:
    """Map a few words to fixed vectors. The same word is used for indexing and search."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        if "alpha" in lowered:
            return [1.0, 0.0, 0.0]
        if "beta" in lowered:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


class FakeLlm:
    def __init__(self, answer: str = "The total is 42.") -> None:
        self.answer = answer
        self.prompts: list[tuple[str, str]] = []
        self.error: AppError | None = None

    def ensure_configured(self) -> None:
        return None

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self.error is not None:
            raise self.error
        self.prompts.append((system_prompt, user_prompt))
        return self.answer


class ScriptedStore:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks

    def search(self, query: str, top_k: int, document_id: str | None = None) -> list[RetrievedChunk]:
        rows = self.chunks
        if document_id is not None:
            rows = [chunk for chunk in rows if chunk.document_id == document_id]
        return rows[:top_k]


def llm_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))
