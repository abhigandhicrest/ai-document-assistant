"""Public document shapes.

These models are what the API returns. They deliberately omit stored file
paths so a caller cannot learn where files live on disk.
"""

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: str = Field(examples=["6b01aec1-a5dc-41ef-ae66-8a93dd4896ae"])
    original_filename: str = Field(examples=["notes.pdf"])
    status: str = Field(examples=["uploaded"])
    message: str = Field(examples=["PDF uploaded. It has not been processed yet."])


class DocumentDetails(BaseModel):
    document_id: str
    original_filename: str
    uploaded_at: str
    status: str
    page_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None


class ProcessResponse(BaseModel):
    document_id: str
    status: str
    page_count: int | None = None
    chunk_count: int | None = None
    message: str


class PageText(BaseModel):
    """Text taken from one PDF page. Page numbers start at 1."""

    page_number: int = Field(ge=1)
    text: str


class TextChunk(BaseModel):
    """A piece of document text small enough to embed and search later."""

    document_id: str
    chunk_index: int = Field(ge=0)
    text: str
    page_numbers: list[int]
