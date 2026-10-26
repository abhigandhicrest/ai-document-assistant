"""PDF extraction and chunking tests.

These call the processing services directly. They do not upload files or
contact a model.
"""

from pathlib import Path

import pytest

from app.schemas.document import PageText
from app.services.document_processor import chunk_pages, extract_pages
from app.utils.exceptions import AppError
from tests.pdf_factory import make_pdf


def test_extracts_text_and_page_numbers(tmp_path: Path) -> None:
    pdf_path = tmp_path / "notes.pdf"
    pdf_path.write_bytes(make_pdf(["Page one total 42", "Page two"]))

    pages = extract_pages(pdf_path)

    assert [(page.page_number, page.text) for page in pages] == [
        (1, "Page one total 42"),
        (2, "Page two"),
    ]


def test_keeps_blank_pages_but_rejects_a_pdf_with_no_text(tmp_path: Path) -> None:
    mixed_path = tmp_path / "mixed.pdf"
    mixed_path.write_bytes(make_pdf(["Visible", ""]))
    pages = extract_pages(mixed_path)
    assert pages[1].page_number == 2
    assert pages[1].text == ""

    blank_path = tmp_path / "blank.pdf"
    blank_path.write_bytes(make_pdf([""]))
    with pytest.raises(AppError, match="no extractable text"):
        extract_pages(blank_path)


def test_reads_a_pdf_that_is_missing_its_xref_table(tmp_path: Path) -> None:
    pdf_path = tmp_path / "minimal.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 55>>stream\n"
        b"BT /F1 18 Tf 40 80 Td (Sample contract total 42) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\r\n"
    )

    pages = extract_pages(pdf_path)

    assert pages[0].page_number == 1
    assert pages[0].text == "Sample contract total 42"


def test_rejects_an_unreadable_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n%%EOF")

    with pytest.raises(AppError, match="could not be read"):
        extract_pages(pdf_path)


def test_chunks_overlap_and_record_every_page_they_touch() -> None:
    pages = [
        PageText(page_number=1, text="AAAAAAAA"),
        PageText(page_number=2, text=""),
        PageText(page_number=3, text="BBBBBBBB"),
    ]

    chunks = chunk_pages(pages, document_id="doc-1", chunk_size=10, overlap=4)

    assert [chunk.text for chunk in chunks] == [
        "AAAAAAAA",
        "AA\n\nBBBBBB",
        "BBBBBB",
    ]
    assert chunks[0].page_numbers == [1]
    assert chunks[1].page_numbers == [1, 3]
    assert chunks[2].page_numbers == [3]
    assert chunks[0].document_id == "doc-1"
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert all(chunk.text.strip() for chunk in chunks)
    assert all(2 not in chunk.page_numbers for chunk in chunks)
    # The next window starts four characters before the previous window ended.
    assert chunks[1].text[:2] == chunks[0].text[-2:]


def test_skips_a_window_that_contains_only_the_page_break() -> None:
    pages = [
        PageText(page_number=1, text="AB"),
        PageText(page_number=2, text="CD"),
    ]

    chunks = chunk_pages(pages, document_id="doc-2", chunk_size=2, overlap=0)

    assert [chunk.text for chunk in chunks] == ["AB", "CD"]


def test_rejects_overlap_that_would_repeat_forever() -> None:
    pages = [PageText(page_number=1, text="hello")]

    with pytest.raises(AppError, match="overlap"):
        chunk_pages(pages, document_id="doc-3", chunk_size=5, overlap=5)
