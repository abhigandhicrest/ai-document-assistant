"""Read text out of a PDF and split it into chunks.

A language model and a vector database work better on short passages than on
a whole file. Chunking cuts the extracted text into overlapping pieces so a
later search can find the passage that matches a question, including words
that sit near a cut. This version reads text embedded in the PDF. It does not
use OCR, so a scanned page with no text layer cannot be read.
"""

import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.schemas.document import PageText, TextChunk
from app.utils.exceptions import AppError


def open_pdf(pdf_path: Path) -> PdfReader:
    """Open a PDF, rebuilding a missing xref table when the file still has objects."""
    try:
        return _checked_reader(PdfReader(str(pdf_path)))
    except AppError:
        raise
    except PyPdfError:
        repaired = _rebuild_xref(pdf_path.read_bytes())
        if repaired is None:
            raise
        return _checked_reader(PdfReader(BytesIO(repaired)))


def extract_pages(pdf_path: Path) -> list[PageText]:
    """Return the text of each page. Empty pages are kept with blank text."""
    try:
        reader = open_pdf(pdf_path)
        pages = [
            PageText(page_number=index, text=page.extract_text() or "")
            for index, page in enumerate(reader.pages, start=1)
        ]
    except AppError:
        raise
    except (PyPdfError, OSError, ValueError) as exc:
        raise AppError("The PDF could not be read.", status_code=400) from exc

    if not pages:
        raise AppError("The PDF has no pages.", status_code=400)
    if not any(page.text.strip() for page in pages):
        raise AppError(
            "This PDF has no extractable text. Scanned documents are not supported.",
            status_code=422,
        )
    return pages


def chunk_pages(
    pages: list[PageText],
    document_id: str,
    chunk_size: int,
    overlap: int,
) -> list[TextChunk]:
    """Split page text into overlapping chunks and remember their page numbers."""
    if chunk_size < 1:
        raise AppError("Chunk size must be at least 1.", status_code=500)
    if overlap < 0 or overlap >= chunk_size:
        raise AppError(
            "Chunk overlap must be zero or smaller than the chunk size.",
            status_code=500,
        )

    full_text, page_spans = _join_pages(pages)
    if not full_text.strip():
        raise AppError(
            "This PDF has no extractable text. Scanned documents are not supported.",
            status_code=422,
        )

    chunks: list[TextChunk] = []
    start = 0
    while start < len(full_text):
        end = min(start + chunk_size, len(full_text))
        text = full_text[start:end].strip()
        if text:
            page_numbers = _pages_for_span(page_spans, start, end)
            chunks.append(
                TextChunk(
                    document_id=document_id,
                    chunk_index=len(chunks),
                    text=text,
                    page_numbers=page_numbers,
                )
            )
        if end >= len(full_text):
            break
        next_start = end - overlap
        # A bad overlap must not keep the window in the same place forever.
        start = end if next_start <= start else next_start

    return chunks


def _checked_reader(reader: PdfReader) -> PdfReader:
    if reader.is_encrypted:
        raise AppError("Encrypted PDFs are not supported.", status_code=400)
    return reader


def _rebuild_xref(data: bytes) -> bytes | None:
    """Add an xref table to a PDF that has objects but no startxref marker."""
    if b"startxref" in data:
        return None
    matches = list(re.finditer(br"(\d+)\s+0\s+obj", data))
    if not matches:
        return None

    offsets = {int(match.group(1)): match.start() for match in matches}
    max_id = max(offsets)
    lines = ["xref", f"0 {max_id + 1}", "0000000000 65535 f "]
    for number in range(1, max_id + 1):
        if number in offsets:
            lines.append(f"{offsets[number]:010d} 00000 n ")
        else:
            lines.append("0000000000 00000 f ")

    trailer_at = data.rfind(b"trailer")
    eof_at = data.rfind(b"%%EOF")
    if trailer_at != -1:
        trailer = data[trailer_at: eof_at if eof_at != -1 else len(data)].strip()
        body = data[:trailer_at].rstrip()
    else:
        trailer = b"trailer<< /Root 1 0 R >>"
        body = data.rstrip(b"%EOF\r\n")
    xref_pos = len(body) + 1
    rebuilt = (
        body
        + b"\n"
        + "\n".join(lines).encode("ascii")
        + b"\n"
        + trailer
        + b"\n"
        + f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return rebuilt


def _join_pages(pages: list[PageText]) -> tuple[str, list[tuple[int, int, int]]]:
    """Join non-empty pages and record which character range belongs to each page."""
    pieces: list[str] = []
    spans: list[tuple[int, int, int]] = []
    cursor = 0

    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        if pieces:
            pieces.append("\n\n")
            cursor += 2
        start = cursor
        pieces.append(text)
        cursor += len(text)
        spans.append((start, cursor, page.page_number))

    return "".join(pieces), spans


def _pages_for_span(
    spans: list[tuple[int, int, int]],
    start: int,
    end: int,
) -> list[int]:
    """List every page that overlaps this character window, in page order."""
    pages = [page for span_start, span_end, page in spans if span_start < end and span_end > start]
    return sorted(set(pages))
