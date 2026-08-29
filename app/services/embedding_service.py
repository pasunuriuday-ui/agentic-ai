import httpx

from app.core.config import settings


class EmbeddingService:
    """
    Generates embeddings using Ollama.
    """

    def __init__(self) -> None:
        self._host = settings.ollama_host.rstrip("/")
        self._model = settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts using Ollama.
        """

        if not texts:
            return []

        vectors: list[list[float]] = []

        try:
            with httpx.Client(timeout=60.0) as client:
                for text in texts:
                    response = client.post(
                        f"{self._host}/api/embed",
                        json={
                            "model": self._model,
                            "input": text,
                        },
                    )

                    response.raise_for_status()

                    data = response.json()
                    embeddings = data.get("embeddings")

                    if not embeddings:
                        raise RuntimeError(
                            "Ollama returned no embeddings"
                        )

                    vectors.append(embeddings[0])

        except Exception as exc:
            raise RuntimeError(
                "Embedding generation failed"
            ) from exc

        return vectors