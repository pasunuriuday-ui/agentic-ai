import logging
import uuid
from pathlib import Path
from typing import List

import fitz
import httpx

logger = logging.getLogger(__name__)


class FileIngestionService:
    """
    Ingest PDF/TXT files into the existing Qdrant knowledge collection.

    This service does NOT delete or recreate the collection.
    """

    def __init__(
        self,
        ollama_url: str,
        qdrant_url: str,
        embed_model: str,
        collection_name: str,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.qdrant_url = qdrant_url.rstrip("/")
        self.embed_model = embed_model
        self.collection_name = collection_name

    # ========================================================
    # TEXT EXTRACTION
    # ========================================================

    def extract_text(
        self,
        filename: str,
        content: bytes,
    ) -> str:

        extension = Path(filename).suffix.lower()

        if extension == ".txt":

            return content.decode(
                "utf-8",
                errors="ignore",
            ).strip()

        if extension == ".pdf":

            text_parts: List[str] = []

            with fitz.open(
                stream=content,
                filetype="pdf",
            ) as document:

                for page in document:

                    page_text = page.get_text(
                        "text"
                    ).strip()

                    if page_text:

                        text_parts.append(
                            page_text
                        )

            return "\n\n".join(
                text_parts
            ).strip()

        raise ValueError(
            "Unsupported file type. "
            "Only PDF and TXT files are supported."
        )

    # ========================================================
    # CHUNKING
    # ========================================================

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1200,
        overlap: int = 200,
    ) -> List[str]:

        if not text.strip():

            return []

        words = text.split()

        chunks = []

        start = 0

        while start < len(words):

            end = min(
                start + chunk_size,
                len(words),
            )

            chunk = " ".join(
                words[start:end]
            ).strip()

            if chunk:

                chunks.append(
                    chunk
                )

            if end >= len(words):

                break

            start = end - overlap

        return chunks

    # ========================================================
    # EMBEDDING
    # ========================================================

    async def get_embedding(
        self,
        client: httpx.AsyncClient,
        text: str,
    ) -> List[float]:

        response = await client.post(
            f"{self.ollama_url}/api/embed",
            json={
                "model": self.embed_model,
                "input": text,
            },
            timeout=60.0,
        )

        response.raise_for_status()

        data = response.json()

        embeddings = data.get(
            "embeddings",
            [],
        )

        if not embeddings:

            raise RuntimeError(
                "Ollama returned no embedding."
            )

        return embeddings[0]

    # ========================================================
    # QDRANT INSERT
    # ========================================================

    async def ingest(
        self,
        filename: str,
        content: bytes,
    ) -> dict:

        text = self.extract_text(
            filename,
            content,
        )

        if not text:

            raise ValueError(
                "No readable text found in the file."
            )

        chunks = self.chunk_text(
            text
        )

        if not chunks:

            raise ValueError(
                "Unable to create document chunks."
            )

        async with httpx.AsyncClient() as client:

            vectors = []

            for chunk in chunks:

                vector = await self.get_embedding(
                    client,
                    chunk,
                )

                vectors.append(
                    vector
                )

            points = []

            for index, (
                chunk,
                vector,
            ) in enumerate(
                zip(chunks, vectors)
            ):

                points.append(
                    {
                        "id": str(
                            uuid.uuid4()
                        ),
                        "vector": vector,
                        "payload": {
                            "text": chunk,
                            "source": filename,
                            "chunk_index": index,
                            "source_type": "uploaded_file",
                        },
                    }
                )

            response = await client.put(
                f"{self.qdrant_url}/collections/"
                f"{self.collection_name}/points"
                f"?wait=true",
                json={
                    "points": points
                },
                timeout=120.0,
            )

            response.raise_for_status()

        logger.info(
            "Ingested %s chunks from %s",
            len(points),
            filename,
        )

        return {
            "success": True,
            "filename": filename,
            "chunks": len(points),
        }