from sentence_transformers import SentenceTransformer
from app.core.config import settings


class EmbeddingService:
    """
    Responsible for generating embeddings from text.
    """

    def __init__(self) -> None:
        self._model = SentenceTransformer(settings.embedding_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()