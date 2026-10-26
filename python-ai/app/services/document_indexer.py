"""Extract, chunk, embed, and index one PDF.

Processing is synchronous. A large PDF keeps the request open until indexing
finishes, which can be slow the first time the embedding model is downloaded.
"""

from pathlib import Path

from app.config import Settings
from app.services.document_processor import chunk_pages, extract_pages
from app.services.embedding_service import EmbeddingService
from app.services.metadata_store import DocumentRecord, MetadataStore
from app.services.vector_store import VectorStore
from app.utils.exceptions import AppError


class DocumentIndexer:
    """Run the steps that move a PDF from uploaded to processed."""

    def __init__(
        self,
        settings: Settings,
        metadata: MetadataStore,
        embedder: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self.settings = settings
        self.metadata = metadata
        self.embedder = embedder
        self.vector_store = vector_store

    def index_pdf(self, record: DocumentRecord, pdf_path: Path) -> DocumentRecord:
        self.metadata.mark(record.document_id, status="processing")
        try:
            pages = extract_pages(pdf_path)
            chunks = chunk_pages(
                pages,
                document_id=record.document_id,
                chunk_size=self.settings.chunk_size,
                overlap=self.settings.chunk_overlap,
            )
            vectors = self.embedder.embed_documents([chunk.text for chunk in chunks])
            self.vector_store.replace(record.document_id, chunks, vectors)
            return self.metadata.mark(
                record.document_id,
                status="processed",
                page_count=len(pages),
                chunk_count=len(chunks),
                error_message=None,
            )
        except AppError as exc:
            self.metadata.mark(record.document_id, status="failed", error_message=exc.message)
            raise
        except Exception as exc:
            self.metadata.mark(
                record.document_id,
                status="failed",
                error_message="The document could not be processed.",
            )
            raise AppError("The document could not be processed.", status_code=500) from exc
