import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
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

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError(
                "Document text must be a non-empty string"
            )

    def to_payload(self) -> Dict[str, Any]:
        """
        Convert the document into a Qdrant payload.

        Reserved fields are protected from metadata collision.
        """

        payload: Dict[str, Any] = {
            "text": self.text
        }

        if self.metadata:
            reserved_keys = {
                "text",
                "_score",
            }

            clean_metadata = {
                key: value
                for key, value in self.metadata.items()
                if key not in reserved_keys
            }

            payload.update(clean_metadata)

        return payload


class RetrievalService:
    """
    Semantic document retrieval using Qdrant vector search.

    Qdrant query_points() returns ScoredPoint objects.
    Each ScoredPoint contains:

        - payload
        - score
        - id

    This service returns the payload together with the Qdrant
    similarity score as '_score'.
    """

    VECTOR_SIZE: int = getattr(
        settings,
        "vector_size",
        768,
    )

    SEARCH_LIMIT: int = getattr(
        settings,
        "search_limit",
        3,
    )

    def __init__(
        self,
        embedder: Optional[EmbeddingService] = None,
        client: Optional[QdrantClient] = None,
    ) -> None:

        self._embedder = (
            embedder
            if embedder is not None
            else EmbeddingService()
        )

        self._client = (
            client
            if client is not None
            else QdrantClient(
                url=settings.qdrant_host
            )
        )

        self._collection_name = (
            settings.collection_name
        )

        self._init_collection()

    # ============================================================
    # COLLECTION INITIALIZATION
    # ============================================================

    def _init_collection(self) -> None:
        """
        Ensure the Qdrant collection exists.
        """

        try:
            exists = self._client.collection_exists(
                collection_name=self._collection_name
            )

            if exists:
                logger.info(
                    "Qdrant collection '%s' already exists",
                    self._collection_name,
                )
                return

            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )

            logger.info(
                "Created Qdrant collection '%s'",
                self._collection_name,
            )

        except UnexpectedResponse as error:

            if "already exists" in str(error).lower():
                logger.info(
                    "Qdrant collection '%s' was created concurrently",
                    self._collection_name,
                )
                return

            logger.error(
                "Collection initialization failed: %s",
                error,
            )

            raise RuntimeError(
                "Failed to initialize vector collection"
            ) from error

        except Exception as error:

            logger.error(
                "Collection initialization failed: %s",
                error,
            )

            raise RuntimeError(
                "Failed to initialize vector collection"
            ) from error

    # ============================================================
    # ADD DOCUMENTS
    # ============================================================

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
    ) -> int:
        """
        Generate embeddings and store documents in Qdrant.

        Every document receives a unique UUID so that adding
        documents never overwrites existing points.
        """

        if not documents:
            raise ValueError(
                "Documents list cannot be empty"
            )

        structured_docs: List[Document] = []

        for index, doc in enumerate(documents):

            if not isinstance(doc, dict):
                raise ValueError(
                    f"Document at index {index} must be a dictionary"
                )

            if "text" not in doc:
                raise ValueError(
                    f"Missing 'text' key in document at index {index}"
                )

            structured_docs.append(
                Document(
                    text=doc["text"],
                    metadata={
                        key: value
                        for key, value in doc.items()
                        if key != "text"
                    },
                )
            )

        texts = [
            document.text
            for document in structured_docs
        ]

        # --------------------------------------------------------
        # Generate embeddings
        # --------------------------------------------------------

        try:

            vectors = self._embedder.embed(
                texts
            )

        except Exception as error:

            logger.error(
                "Embedding failed: %s",
                error,
            )

            raise RuntimeError(
                "Embedding generation failed"
            ) from error

        # --------------------------------------------------------
        # Validate embedding count
        # --------------------------------------------------------

        if len(vectors) != len(structured_docs):

            raise RuntimeError(
                "Embedding count does not match document count"
            )

        # --------------------------------------------------------
        # Validate embedding dimensions
        # --------------------------------------------------------

        for index, vector in enumerate(vectors):

            if len(vector) != self.VECTOR_SIZE:

                raise RuntimeError(
                    "Invalid embedding dimension for document "
                    f"{index}: expected {self.VECTOR_SIZE}, "
                    f"got {len(vector)}"
                )

        # --------------------------------------------------------
        # Create Qdrant points
        # --------------------------------------------------------

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vectors[index],
                payload=structured_docs[index].to_payload(),
            )
            for index in range(
                len(structured_docs)
            )
        ]

        # --------------------------------------------------------
        # Upsert
        # --------------------------------------------------------

        try:

            self._client.upsert(
                collection_name=self._collection_name,
                points=points,
            )

            logger.info(
                "Indexed %d documents",
                len(points),
            )

            return len(points)

        except Exception as error:

            logger.error(
                "Upsert failed: %s",
                error,
            )

            raise RuntimeError(
                "Failed to store documents"
            ) from error

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        query: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic vector search against Qdrant.

        The installed Qdrant client in this project exposes
        query_points(), not search().

        query_points() returns ScoredPoint objects.

        Each result contains:

            {
                "text": "...",
                "_score": 0.799...
            }

        The '_score' value is copied directly from:

            point.score
        """

        # --------------------------------------------------------
        # Validate query
        # --------------------------------------------------------

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "Query cannot be empty"
            )

        search_limit = (
            limit
            if limit is not None
            else self.SEARCH_LIMIT
        )

        if search_limit <= 0:
            raise ValueError(
                "Search limit must be greater than zero"
            )

        # --------------------------------------------------------
        # Generate query embedding
        # --------------------------------------------------------

        try:

            query_vectors = self._embedder.embed(
                [query]
            )

            if not query_vectors:

                raise RuntimeError(
                    "Embedding service returned no vector"
                )

            query_vector = query_vectors[0]

        except Exception as error:

            logger.error(
                "Query embedding failed: %s",
                error,
            )

            raise RuntimeError(
                "Query embedding failed"
            ) from error

        # --------------------------------------------------------
        # Validate query vector
        # --------------------------------------------------------

        if len(query_vector) != self.VECTOR_SIZE:

            raise RuntimeError(
                "Invalid query embedding dimension: "
                f"expected {self.VECTOR_SIZE}, "
                f"got {len(query_vector)}"
            )

        # --------------------------------------------------------
        # Query Qdrant
        # --------------------------------------------------------
        #
        # IMPORTANT:
        #
        # Do NOT use:
        #
        #     self._client.search(...)
        #
        # because the installed QdrantClient in this environment
        # does not expose that method.
        #
        # Use:
        #
        #     self._client.query_points(...)
        #
        # and extract:
        #
        #     point.payload
        #     point.score
        #
        # The score must be explicitly copied into '_score'.
        # --------------------------------------------------------

        try:

            response = self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                limit=search_limit,
                with_payload=True,
                with_vectors=False,
            )

        except Exception as error:

            logger.error(
                "Search failed: %s",
                error,
            )

            raise RuntimeError(
                "Vector search failed"
            ) from error

        # --------------------------------------------------------
        # Validate Qdrant response
        # --------------------------------------------------------

        if response is None:

            logger.warning(
                "Qdrant returned None for query: %s",
                query[:50],
            )

            return []

        # --------------------------------------------------------
        # Extract points
        # --------------------------------------------------------

        points = getattr(
            response,
            "points",
            None,
        )

        if points is None:

            logger.warning(
                "Qdrant response contains no points for query: %s",
                query[:50],
            )

            return []

        # --------------------------------------------------------
        # Convert ScoredPoint objects into dictionaries
        # --------------------------------------------------------

        documents: List[Dict[str, Any]] = []

        for point in points:

            # ----------------------------------------------------
            # Extract payload
            # ----------------------------------------------------

            if isinstance(point, dict):

                payload = (
                    point.get("payload")
                    or {}
                )

            else:

                payload = (
                    getattr(
                        point,
                        "payload",
                        None,
                    )
                    or {}
                )

            if not payload:
                continue

            # ----------------------------------------------------
            # Extract Qdrant similarity score
            # ----------------------------------------------------

            if isinstance(point, dict):

                score = point.get(
                    "score"
                )

            else:

                score = getattr(
                    point,
                    "score",
                    None,
                )

            # ----------------------------------------------------
            # Build result dictionary
            # ----------------------------------------------------

            document: Dict[str, Any] = dict(
                payload
            )

            # ----------------------------------------------------
            # IMPORTANT FIX
            # ----------------------------------------------------
            #
            # Qdrant:
            #
            #     point.score
            #
            # becomes:
            #
            #     document["_score"]
            #
            # Therefore:
            #
            #     result["_score"]
            #
            # will contain the actual similarity score.
            # ----------------------------------------------------

            document["_score"] = score

            documents.append(
                document
            )

        # --------------------------------------------------------
        # No usable documents
        # --------------------------------------------------------

        if not documents:

            logger.warning(
                "No usable results for query: %s",
                query[:50],
            )

            return []

        # --------------------------------------------------------
        # Logging
        # --------------------------------------------------------

        logger.info(
            "Retrieved %d documents for query: %s",
            len(documents),
            query,
        )

        for index, document in enumerate(
            documents,
            start=1,
        ):

            logger.debug(
                "Result %d score=%s text=%s",
                index,
                document.get("_score"),
                document.get(
                    "text",
                    "",
                )[:100],
            )

        return documents

    # ============================================================
    # COUNT
    # ============================================================

    def count(self) -> int:
        """
        Return the number of points currently stored
        in the Qdrant collection.
        """

        try:

            info = self._client.get_collection(
                self._collection_name
            )

            return info.points_count or 0

        except Exception as error:

            logger.error(
                "Count failed: %s",
                error,
            )

            return 0
