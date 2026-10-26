"""SQLite record of uploaded documents.

Laravel keeps its own user database. This service keeps a separate record of
files the Python API has accepted, including processing status. The stored
filename stays inside this module and is not part of API responses.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DocumentRecord:
    document_id: str
    original_filename: str
    stored_filename: str
    uploaded_at: str
    status: str
    page_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None


class MetadataStore:
    """Small document registry stored at METADATA_DB_PATH."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    def create(
        self,
        document_id: str,
        original_filename: str,
        stored_filename: str,
    ) -> DocumentRecord:
        uploaded_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    id, original_filename, stored_filename, uploaded_at, status
                ) VALUES (?, ?, ?, ?, 'uploaded')
                """,
                (document_id, original_filename, stored_filename, uploaded_at),
            )
        record = self.get(document_id)
        if record is None:
            raise RuntimeError("The document record was not saved.")
        return record

    def list_documents(self) -> list[DocumentRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents ORDER BY uploaded_at DESC"
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def mark(
        self,
        document_id: str,
        status: str,
        page_count: int | None = None,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> DocumentRecord:
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE documents
                SET status = ?, page_count = ?, chunk_count = ?, error_message = ?
                WHERE id = ?
                """,
                (status, page_count, chunk_count, error_message, document_id),
            )
            if updated.rowcount != 1:
                raise RuntimeError("The document record was not updated.")
        record = self.get(document_id)
        if record is None:
            raise RuntimeError("The document record was not updated.")
        return record

    def delete(self, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    def get(self, document_id: str) -> DocumentRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def _create_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    page_count INTEGER,
                    chunk_count INTEGER,
                    error_message TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_record(self, row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            document_id=row["id"],
            original_filename=row["original_filename"],
            stored_filename=row["stored_filename"],
            uploaded_at=row["uploaded_at"],
            status=row["status"],
            page_count=row["page_count"],
            chunk_count=row["chunk_count"],
            error_message=row["error_message"],
        )
