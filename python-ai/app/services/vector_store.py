"""Persistent ChromaDB index of document chunks.

Embeddings are calculated by the embedding service and stored with the chunk
text, document id, and page numbers. Search can be limited to one document.
Re-indexing a document replaces its old chunks instead of adding duplicates.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from app.schemas.document import TextChunk
from app.utils.exceptions import AppError

_CLIENTS: dict[str, object] = {}


@dataclass
class RetrievedChunk:
    document_id: str
    chunk_index: int
    text: str
    page_numbers: list[int]


class VectorStore:
    """Local vector collection stored under CHROMA_PERSIST_DIR."""

    def __init__(self, persist_dir: Path, embedder: object) -> None:
        self.persist_dir = persist_dir
        self.embedder = embedder

    def replace(self, document_id: str, chunks: list[TextChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise AppError("Embeddings could not be saved for every chunk.", status_code=500)
        self.delete_document(document_id)
        if not chunks:
            return
        collection = self._collection()
        try:
            collection.add(
                ids=[f"{document_id}:{chunk.chunk_index}" for chunk in chunks],
                embeddings=vectors,
                documents=[chunk.text for chunk in chunks],
                metadatas=[self._metadata(chunk) for chunk in chunks],
            )
        except Exception as exc:
            raise AppError(
                "The vector store could not save this document. "
                "If the embedding model changed, delete storage/chroma and process the document again.",
                status_code=500,
            ) from exc

    def search(self, query: str, top_k: int, document_id: str | None = None) -> list[RetrievedChunk]:
        collection = self._collection()
        try:
            total = collection.count()
        except Exception as exc:
            raise AppError("The document search failed.", status_code=500) from exc
        if total == 0 or top_k < 1:
            return []

        where = {"document_id": document_id} if document_id else None
        try:
            result = collection.query(
                query_embeddings=[self.embedder.embed_query(query)],
                n_results=min(top_k, total),
                where=where,
            )
        except Exception as exc:
            message = str(exc).lower()
            if "no" in message or "0" in message:
                return []
            raise AppError("The document search failed.", status_code=500) from exc

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        found: list[RetrievedChunk] = []
        for index, chunk_id in enumerate(ids):
            if not chunk_id:
                continue
            metadata = metadatas[index] or {}
            found.append(
                RetrievedChunk(
                    document_id=str(metadata.get("document_id", "")),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    text=documents[index] or "",
                    page_numbers=_parse_pages(str(metadata.get("page_numbers", ""))),
                )
            )
        return found

    def delete_document(self, document_id: str) -> None:
        collection = self._collection()
        try:
            existing = collection.get(where={"document_id": document_id})
            ids = existing.get("ids") or []
            if ids:
                collection.delete(ids=ids)
        except Exception as exc:
            raise AppError("The indexed document could not be removed.", status_code=500) from exc

    def count(self, document_id: str | None = None) -> int:
        collection = self._collection()
        if document_id is None:
            return int(collection.count())
        existing = collection.get(where={"document_id": document_id})
        return len(existing.get("ids") or [])

    def _collection(self) -> object:
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        key = str(self.persist_dir.resolve())
        client = _CLIENTS.get(key)
        if client is None:
            os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
            try:
                import chromadb

                client = chromadb.PersistentClient(path=key)
            except Exception as exc:
                raise AppError("The vector store could not be opened.", status_code=500) from exc
            _CLIENTS[key] = client
        try:
            return client.get_or_create_collection(
                name="document_chunks",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise AppError("The vector store could not be opened.", status_code=500) from exc

    def _metadata(self, chunk: TextChunk) -> dict[str, str | int]:
        return {
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "page_numbers": ",".join(str(page) for page in chunk.page_numbers),
        }


def _parse_pages(value: str) -> list[int]:
    pages: list[int] = []
    for part in value.split(","):
        if part.isdigit():
            pages.append(int(part))
    return pages
