import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    VectorParams,
    Distance,
)

from app.core.config import settings
from app.services.embedding_service import EmbeddingService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Document:
    """
    Structured document with text and optional metadata.
    """

    text: str
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.text or not self.text.strip():
            raise ValueError("Document text cannot be empty")

    def to_payload(self) -> Dict[str, Any]:
        payload = {"text": self.text}

        if self.metadata:
            payload.update(self.metadata)

        return payload


class RetrievalService:
    """
    Semantic document retrieval using Qdrant vector search.
    """

    VECTOR_SIZE: int = 768
    SEARCH_LIMIT: int = 3

    def __init__(
        self,
        embedder: Optional[EmbeddingService] = None,
        client: Optional[QdrantClient] = None,
    ) -> None:
        self._embedder = embedder or EmbeddingService()
        self._client = client or QdrantClient(":memory:")
        self._collection_name = settings.collection_name

        self._init_collection()

    def _init_collection(self) -> None:
        """
        Initialize the Qdrant collection without using the
        deprecated recreate_collection() method.
        """

        try:
            # Check whether the collection already exists.
            if self._client.collection_exists(
                collection_name=self._collection_name
            ):
                # Delete the existing collection so the test/demo
                # environment starts with a clean collection.
                self._client.delete_collection(
                    collection_name=self._collection_name
                )

            # Create the collection using the current Qdrant API.
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )

            logger.info(
                f"Collection '{self._collection_name}' initialized"
            )

        except Exception as e:
            logger.error(
                f"Collection init failed: {e}"
            )

            raise RuntimeError(
                "Failed to initialize vector collection"
            ) from e

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
    ) -> int:
        if not documents:
            raise ValueError(
                "Documents list cannot be empty"
            )

        structured_docs: List[Document] = []

        for i, doc in enumerate(documents):

            if "text" not in doc:
                raise ValueError(
                    f"Missing 'text' in document {i}"
                )

            structured_docs.append(
                Document(
                    text=doc["text"],
                    metadata={
                        k: v
                        for k, v in doc.items()
                        if k != "text"
                    },
                )
            )

        texts = [
            document.text
            for document in structured_docs
        ]

        try:
            vectors = self._embedder.embed(texts)

        except Exception as e:
            logger.error(
                f"Embedding failed: {e}"
            )

            raise RuntimeError(
                "Embedding generation failed"
            ) from e

        points = [
            PointStruct(
                id=i,
                vector=vectors[i],
                payload=structured_docs[i].to_payload(),
            )
            for i in range(len(structured_docs))
        ]

        try:
            self._client.upsert(
                collection_name=self._collection_name,
                points=points,
            )

            logger.info(
                f"Indexed {len(points)} documents"
            )

            return len(points)

        except Exception as e:
            logger.error(
                f"Upsert failed: {e}"
            )

            raise RuntimeError(
                "Failed to store documents"
            ) from e

    def search(
        self,
        query: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        if not query or not query.strip():
            raise ValueError(
                "Query cannot be empty"
            )

        search_limit = (
            limit or self.SEARCH_LIMIT
        )

        # Generate query embedding.
        try:
            vector = self._embedder.embed(
                [query]
            )[0]

        except Exception as e:
            logger.error(
                f"Query embedding failed: {e}"
            )

            raise RuntimeError(
                "Query embedding failed"
            ) from e

        # Search Qdrant.
        try:
            results = self._client.query_points(
                collection_name=self._collection_name,
                query=vector,
                limit=search_limit,
            )

        except Exception as e:
            logger.error(
                f"Search failed: {e}"
            )

            raise RuntimeError(
                "Vector search failed"
            ) from e

        # Extract payloads safely.
        documents = [
            point.payload
            for point in results.points
            if point.payload
        ]

        if not documents:
            logger.warning(
                f"No results for query: {query[:50]}"
            )

        return documents

    def count(self) -> int:
        try:
            info = self._client.get_collection(
                self._collection_name
            )

            return info.points_count

        except Exception as e:
            logger.error(
                f"Count failed: {e}"
            )

            return 0