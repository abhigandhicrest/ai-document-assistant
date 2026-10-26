"""Turn text into vectors with a Sentence Transformers model.

The model is loaded the first time a document is indexed or a question is
embedded, then kept in memory. The health check does not use this module's
model, so the API can start before the download finishes.
"""

from app.utils.exceptions import AppError

_MODELS: dict[str, object] = {}


class EmbeddingService:
    """One embedding model shared by indexing and question search."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = self._model()
        try:
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:
            raise AppError(
                "The embedding model could not read this text.",
                status_code=500,
            ) from exc
        return [vector.tolist() for vector in vectors]

    def _model(self) -> object:
        cached = _MODELS.get(self.model_name)
        if cached is not None:
            return cached
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name)
        except Exception as exc:
            raise AppError(
                "The embedding model could not be loaded. Check the network and EMBEDDING_MODEL.",
                status_code=503,
            ) from exc
        _MODELS[self.model_name] = model
        return model
