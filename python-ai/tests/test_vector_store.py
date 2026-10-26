"""ChromaDB tests. They use a temporary folder and a fake embedder."""

from app.schemas.document import TextChunk
from app.services.vector_store import VectorStore
from tests.fakes import KeywordEmbedder


def _chunk(document_id: str, index: int, text: str) -> TextChunk:
    return TextChunk(
        document_id=document_id,
        chunk_index=index,
        text=text,
        page_numbers=[index + 1],
    )


def test_indexes_and_retrieves_the_matching_document(tmp_path) -> None:
    store = VectorStore(tmp_path / "chroma", KeywordEmbedder())
    store.replace("doc-a", [_chunk("doc-a", 0, "alpha contract total")], [[1.0, 0.0, 0.0]])
    store.replace("doc-b", [_chunk("doc-b", 0, "beta weather report")], [[0.0, 1.0, 0.0]])

    found = store.search("alpha contract", top_k=2)

    assert found[0].document_id == "doc-a"
    assert found[0].page_numbers == [1]
    assert store.count() == 2


def test_can_restrict_search_to_one_document(tmp_path) -> None:
    store = VectorStore(tmp_path / "chroma", KeywordEmbedder())
    store.replace("doc-a", [_chunk("doc-a", 0, "alpha contract")], [[1.0, 0.0, 0.0]])
    store.replace("doc-b", [_chunk("doc-b", 0, "beta weather")], [[0.0, 1.0, 0.0]])

    found = store.search("alpha contract", top_k=2, document_id="doc-b")

    assert [chunk.document_id for chunk in found] == ["doc-b"]


def test_empty_collection_returns_no_chunks(tmp_path) -> None:
    store = VectorStore(tmp_path / "chroma", KeywordEmbedder())

    assert store.search("alpha", top_k=3) == []


def test_reindexing_replaces_old_chunks(tmp_path) -> None:
    store = VectorStore(tmp_path / "chroma", KeywordEmbedder())
    store.replace("doc-a", [_chunk("doc-a", 0, "alpha one")], [[1.0, 0.0, 0.0]])
    store.replace(
        "doc-a",
        [_chunk("doc-a", 0, "alpha two"), _chunk("doc-a", 1, "alpha three")],
        [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
    )

    assert store.count("doc-a") == 2
    assert store.search("alpha", top_k=5, document_id="doc-a")[0].text == "alpha two"


def test_delete_removes_only_that_document(tmp_path) -> None:
    store = VectorStore(tmp_path / "chroma", KeywordEmbedder())
    store.replace("doc-a", [_chunk("doc-a", 0, "alpha")], [[1.0, 0.0, 0.0]])
    store.replace("doc-b", [_chunk("doc-b", 0, "beta")], [[0.0, 1.0, 0.0]])

    store.delete_document("doc-a")

    assert store.count("doc-a") == 0
    assert store.count("doc-b") == 1
