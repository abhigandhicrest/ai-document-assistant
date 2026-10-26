"""FastAPI application entry point.

Routes, settings, and error handling live in their own modules. This file
only assembles them. Embeddings and question answering are not registered yet.
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.ask import router as ask_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.config import get_settings
from app.utils.exceptions import AppError

app = FastAPI(
    title="AI Document Assistant",
    description=(
        "Use these pages to call the Python API and inspect the response.\n\n"
        "Open `/docs`, choose an operation, then **Try it out**.\n\n"
        "Working calls:\n"
        "- `GET /api/health` checks that this process is running.\n"
        "- `POST /api/documents/upload` stores one PDF.\n"
        "- `POST /api/documents/{document_id}/process` extracts text, creates embeddings, and indexes it.\n"
        "- `POST /api/chat/ask` answers from indexed documents.\n"
        "- `POST /ask` is the call the Laravel site already makes. It indexes that PDF if needed, "
        "then asks the configured language model.\n\n"
        "Set `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` before expecting a model answer. "
        "The health check does not load the embedding model or require those settings."
    ),
    version="0.1.0",
    servers=[{"url": "http://127.0.0.1:8001", "description": "Local Python API"}],
)

app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(documents_router, prefix="/api", tags=["Documents"])
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(ask_router, tags=["Laravel"])


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    """Reject a bad request without echoing internal details."""
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "The request is not valid."},
    )


@app.exception_handler(AppError)
async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    """Return a known error message without a stack trace or file path."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    """Hide unexpected failure details from API clients."""
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "The service could not complete this request.",
        },
    )


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
    )
