"""Question endpoint for a document that has already been indexed."""

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.dependencies import get_metadata_store, get_rag, require_api_token, top_k_for
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.responses import ErrorResponse
from app.services.metadata_store import MetadataStore
from app.services.rag_pipeline import RagPipeline
from app.utils.exceptions import AppError

router = APIRouter(dependencies=[Depends(require_api_token)])


@router.post(
    "/chat/ask",
    response_model=ChatResponse,
    summary="Ask a question about indexed documents",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def ask_question(
    body: ChatRequest,
    metadata: MetadataStore = Depends(get_metadata_store),
    rag: RagPipeline = Depends(get_rag),
) -> ChatResponse:
    """Search indexed passages and ask the configured language model."""
    rag.llm.ensure_configured()
    if body.document_id is not None:
        record = metadata.get(body.document_id)
        if record is None:
            raise AppError("The document was not found.", status_code=404)
        if record.status != "processed":
            raise AppError("The document has not been processed yet.", status_code=409)

    result = rag.answer(
        body.question,
        document_id=body.document_id,
        top_k=top_k_for(get_settings(), body.top_k),
    )
    return ChatResponse(
        status="success",
        answer=result.answer,
        retrieved_chunk_count=result.retrieved_chunk_count,
        sources=result.sources,
    )
