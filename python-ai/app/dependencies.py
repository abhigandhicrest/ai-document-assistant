"""Build the services each request needs.

Routes ask FastAPI for these functions. Tests replace them so they can run
without downloading a model or calling a language-model API.
"""

import secrets
from typing import Annotated

from fastapi import Depends, Header

from app.config import Settings, get_settings
from app.services.document_indexer import DocumentIndexer
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LlmService
from app.services.metadata_store import MetadataStore
from app.services.rag_pipeline import RagPipeline
from app.services.vector_store import VectorStore
from app.utils.exceptions import AppError


def require_api_token(authorization: Annotated[str | None, Header()] = None) -> None:
    """Require a bearer token only when API_TOKEN is configured."""
    expected = get_settings().api_token.strip()
    if expected == "":
        return
    provided = authorization or ""
    valid = provided == f"Bearer {expected}" and secrets.compare_digest(provided, f"Bearer {expected}")
    if not valid:
        raise AppError("A valid API token is required.", status_code=401)


def get_metadata_store() -> MetadataStore:
    settings = get_settings()
    return MetadataStore(settings.path_inside_project(settings.metadata_db_path))


def get_embedder() -> EmbeddingService:
    return EmbeddingService(get_settings().embedding_model)


def get_vector_store(embedder: EmbeddingService = Depends(get_embedder)) -> VectorStore:
    settings = get_settings()
    return VectorStore(settings.path_inside_project(settings.chroma_persist_dir), embedder)


def get_llm() -> LlmService:
    settings = get_settings()
    return LlmService(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def get_indexer(
    metadata: MetadataStore = Depends(get_metadata_store),
    embedder: EmbeddingService = Depends(get_embedder),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentIndexer:
    return DocumentIndexer(get_settings(), metadata, embedder, vector_store)


def get_rag(
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LlmService = Depends(get_llm),
) -> RagPipeline:
    return RagPipeline(vector_store, llm)


def top_k_for(settings: Settings, requested: int | None) -> int:
    limit = 10
    chosen = settings.top_k if requested is None else requested
    return max(1, min(chosen, limit))
