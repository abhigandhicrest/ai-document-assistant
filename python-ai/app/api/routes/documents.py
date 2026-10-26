"""Document upload route.

The caller sends a PDF. This route checks that it really is a PDF, saves it
under a generated name, and records that it was uploaded. Reading the text
and splitting it into chunks are available as services; indexing comes later.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from pypdf.errors import PyPdfError

from app.config import get_settings
from app.dependencies import get_indexer, get_metadata_store, get_vector_store, require_api_token
from app.schemas.document import DocumentDetails, DocumentUploadResponse, ProcessResponse
from app.schemas.responses import ErrorResponse
from app.services.document_indexer import DocumentIndexer
from app.services.document_processor import open_pdf
from app.services.metadata_store import DocumentRecord, MetadataStore
from app.services.vector_store import VectorStore
from app.utils.exceptions import AppError

router = APIRouter(dependencies=[Depends(require_api_token)])
_READ_SIZE = 1024 * 1024


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    summary="Upload one PDF",
    responses={
        400: {
            "model": ErrorResponse,
            "description": "The file is missing, empty, or not a readable PDF.",
        },
        413: {
            "model": ErrorResponse,
            "description": "The PDF is larger than MAX_UPLOAD_SIZE_MB.",
        },
    },
)
async def upload_document(
    file: UploadFile = File(..., description="One PDF. The filename must end with .pdf."),
) -> DocumentUploadResponse:
    """Store a PDF and return its document id.

    Send the file as multipart form field `file`. The response does not include
    the folder where the file was saved. Status `uploaded` means the file is
    stored only. It is not indexed, and this call does not answer questions.
    """
    original_filename = display_filename(file.filename)
    settings = get_settings()
    upload_dir = settings.path_inside_project(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    document_id = str(uuid.uuid4())
    stored_filename = f"{document_id}.pdf"
    destination = upload_dir / stored_filename
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    try:
        await _write_upload(file, destination, max_bytes)
        _require_readable_pdf(destination)
        MetadataStore(settings.path_inside_project(settings.metadata_db_path)).create(
            document_id=document_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return DocumentUploadResponse(
        document_id=document_id,
        original_filename=original_filename,
        status="uploaded",
        message="PDF uploaded. It has not been processed yet.",
    )


def _details(record: DocumentRecord) -> DocumentDetails:
    return DocumentDetails(
        document_id=record.document_id,
        original_filename=record.original_filename,
        uploaded_at=record.uploaded_at,
        status=record.status,
        page_count=record.page_count,
        chunk_count=record.chunk_count,
        error_message=record.error_message,
    )


@router.get("/documents", response_model=list[DocumentDetails], summary="List documents")
def list_documents(metadata: MetadataStore = Depends(get_metadata_store)) -> list[DocumentDetails]:
    """Return upload records without filesystem paths."""
    return [_details(record) for record in metadata.list_documents()]


@router.get("/documents/{document_id}", response_model=DocumentDetails, summary="Get one document")
def get_document(document_id: str, metadata: MetadataStore = Depends(get_metadata_store)) -> DocumentDetails:
    """Return status and counts for one document."""
    record = _require_document(metadata, document_id)
    return _details(record)


@router.post(
    "/documents/{document_id}/process",
    response_model=ProcessResponse,
    summary="Extract, embed, and index a document",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def process_document(
    document_id: str,
    metadata: MetadataStore = Depends(get_metadata_store),
    indexer: DocumentIndexer = Depends(get_indexer),
) -> ProcessResponse:
    """Index one uploaded PDF. The request waits until indexing finishes."""
    record = _require_document(metadata, document_id)
    pdf_path = _uploaded_pdf(record)
    if not pdf_path.is_file():
        metadata.mark(document_id, status="failed", error_message="The uploaded file is missing.")
        raise AppError("The uploaded file is missing.", status_code=404)
    updated = indexer.index_pdf(record, pdf_path)
    return ProcessResponse(
        document_id=updated.document_id,
        status=updated.status,
        page_count=updated.page_count,
        chunk_count=updated.chunk_count,
        message="Document processed.",
    )


@router.delete(
    "/documents/{document_id}",
    summary="Delete a document",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def delete_document(
    document_id: str,
    metadata: MetadataStore = Depends(get_metadata_store),
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict[str, str]:
    """Remove the index, the metadata row, and a file stored by this API."""
    record = _require_document(metadata, document_id)
    vector_store.delete_document(document_id)
    pdf_path = _uploaded_pdf(record)
    if pdf_path.is_file():
        pdf_path.unlink()
    metadata.delete(document_id)
    return {"status": "success", "message": "Document deleted."}


def _require_document(metadata: MetadataStore, document_id: str) -> DocumentRecord:
    if not _safe_document_id(document_id):
        raise AppError("The document id is not valid.", status_code=400)
    record = metadata.get(document_id)
    if record is None:
        raise AppError("The document was not found.", status_code=404)
    return record


def _safe_document_id(document_id: str) -> bool:
    return bool(document_id) and document_id.replace("-", "").replace("_", "").isalnum()


def _uploaded_pdf(record: DocumentRecord) -> Path:
    stored_name = Path(record.stored_filename).name
    if stored_name != record.stored_filename:
        raise AppError("The document record is not valid.", status_code=400)
    return get_settings().path_inside_project(get_settings().upload_dir) / stored_name


def display_filename(filename: str | None) -> str:
    """Keep only the file's own name, never a directory path from the client."""
    if filename is None or not filename.strip():
        raise AppError("A PDF file is required.", status_code=400)

    safe_name = Path(filename.replace("\\", "/")).name.replace("\x00", "").strip()
    if not safe_name.lower().endswith(".pdf") or safe_name in {".pdf"}:
        raise AppError("Only PDF files are accepted.", status_code=400)
    return safe_name[:255]


async def _write_upload(file: UploadFile, destination: Path, max_bytes: int) -> int:
    """Copy the upload to disk in pieces and stop if it grows past the limit."""
    size = 0
    header = bytearray()

    with destination.open("wb") as stored:
        while True:
            piece = await file.read(_READ_SIZE)
            if not piece:
                break
            size += len(piece)
            if size > max_bytes:
                raise AppError("The PDF is larger than the upload limit.", status_code=413)
            if len(header) < 5:
                header.extend(piece[: 5 - len(header)])
            stored.write(piece)

    if size == 0:
        raise AppError("The uploaded file is empty.", status_code=400)
    if header[:5] != b"%PDF-":
        raise AppError("The file is not a valid PDF.", status_code=400)
    return size


def _require_readable_pdf(path: Path) -> None:
    """Open the saved file with PyPDF so a renamed non-PDF is rejected."""
    try:
        reader = open_pdf(path)
        if len(reader.pages) == 0:
            raise AppError("The PDF has no pages.", status_code=400)
    except AppError:
        raise
    except (PyPdfError, OSError, ValueError) as exc:
        raise AppError("The file is not a valid PDF.", status_code=400) from exc
