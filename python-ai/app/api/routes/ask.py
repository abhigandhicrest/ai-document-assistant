"""Laravel question endpoint.

The website posts here with the document id it already stores and the private
path of the PDF. This route indexes that file when needed, then uses the same
retrieval and language-model steps as /api/chat/ask.
"""

from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.routes.documents import display_filename
from app.config import get_settings
from app.dependencies import get_indexer, get_metadata_store, get_rag, require_api_token, top_k_for
from app.schemas.chat import LaravelAskRequest, LaravelAskResponse
from app.schemas.responses import ErrorResponse
from app.services.document_indexer import DocumentIndexer
from app.services.metadata_store import MetadataStore
from app.services.rag_pipeline import RagPipeline
from app.utils.exceptions import AppError

router = APIRouter(dependencies=[Depends(require_api_token)])


@router.post(
    "/ask",
    response_model=LaravelAskResponse,
    summary="Answer a Laravel document question",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def ask_for_laravel(
    body: LaravelAskRequest,
    metadata: MetadataStore = Depends(get_metadata_store),
    indexer: DocumentIndexer = Depends(get_indexer),
    rag: RagPipeline = Depends(get_rag),
) -> LaravelAskResponse:
    """Index the Laravel PDF if needed, then answer from its text."""
    rag.llm.ensure_configured()
    pdf_path = resolve_laravel_pdf(body.storage_path)
    document_id = f"laravel-{body.user_id}-{body.document_id}"
    record = metadata.get(document_id)
    if record is None:
        record = metadata.create(
            document_id=document_id,
            original_filename=_original_name(body.filename),
            stored_filename=f"{document_id}.pdf",
        )
    if record.status != "processed":
        indexer.index_pdf(record, pdf_path)

    result = rag.answer(
        body.question,
        document_id=document_id,
        top_k=top_k_for(get_settings(), None),
    )
    return LaravelAskResponse(
        answer=result.answer,
        meta={
            "document_id": document_id,
            "retrieved_chunk_count": result.retrieved_chunk_count,
            "sources": [source.model_dump() for source in result.sources],
        },
    )


def resolve_laravel_pdf(storage_path: str) -> Path:
    """Find a PDF inside Laravel's private storage without following a user path outside it."""
    relative = storage_path.replace("\\", "/").strip()
    if relative.startswith("/") or ":" in relative:
        raise AppError("The document path is not valid.", status_code=400)
    parts = Path(relative).parts
    if not parts or any(part in {"..", ".", ""} for part in parts):
        raise AppError("The document path is not valid.", status_code=400)

    root = get_settings().path_inside_project(get_settings().laravel_storage_dir).resolve()
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root):
        raise AppError("The document path is not valid.", status_code=400)
    if candidate.suffix.lower() != ".pdf" or not candidate.is_file():
        raise AppError("The document file could not be found.", status_code=404)
    return candidate


def _original_name(filename: str) -> str:
    try:
        return display_filename(filename)
    except AppError:
        return "document.pdf"
