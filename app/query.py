import asyncio
import os
import sys
from typing import List

import httpx

from app.core.config import settings


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = settings.ollama_host.rstrip("/")

QDRANT_URL = settings.qdrant_host.rstrip("/")

EMBED_MODEL = settings.embedding_model

LLM_MODEL = settings.llm_model

COLLECTION_NAME = settings.collection_name

TOP_K = int(
    os.getenv("TOP_K", "2")
)


# ============================================================
# OLLAMA HEALTH CHECK
# ============================================================

async def check_ollama(client: httpx.AsyncClient) -> None:
    """Verify that Ollama is reachable and required models exist."""

    try:
        response = await client.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=10.0
        )

        response.raise_for_status()

        data = response.json()

        models = {
            model.get("name", "")
            for model in data.get("models", [])
        }

        required_models = {
            EMBED_MODEL,
            f"{EMBED_MODEL}:latest",
            LLM_MODEL,
            f"{LLM_MODEL}:latest",
        }

        found_embedding = any(
            model.startswith(EMBED_MODEL)
            for model in models
        )

        found_llm = any(
            model.startswith(LLM_MODEL)
            for model in models
        )

        if not found_embedding:
            raise RuntimeError(
                f"Embedding model '{EMBED_MODEL}' "
                f"was not found in Ollama.\n"
                f"Available models: {sorted(models)}"
            )

        if not found_llm:
            raise RuntimeError(
                f"LLM model '{LLM_MODEL}' "
                f"was not found in Ollama.\n"
                f"Available models: {sorted(models)}"
            )

        print("Ollama: OK")
        print(f"Embedding model: {EMBED_MODEL}")
        print(f"LLM model: {LLM_MODEL}")

    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Cannot connect to Ollama at {OLLAMA_URL}\n"
            f"Error: {exc}"
        ) from exc


# ============================================================
# QDRANT HEALTH CHECK
# ============================================================

async def check_qdrant(client: httpx.AsyncClient) -> None:
    """Verify that Qdrant is reachable."""

    try:
        response = await client.get(
            f"{QDRANT_URL}/collections",
            timeout=10.0
        )

        response.raise_for_status()

        print("Qdrant: OK")

    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Cannot connect to Qdrant at {QDRANT_URL}\n"
            f"Error: {exc}"
        ) from exc


# ============================================================
# EMBEDDING
# ============================================================

async def get_embedding(
    client: httpx.AsyncClient,
    text: str
) -> List[float]:
    """
    Generate an embedding using Ollama.

    Primary endpoint:
        /api/embed

    Fallback:
        /api/embeddings
    """

    # --------------------------------------------------------
    # Modern Ollama embedding endpoint
    # --------------------------------------------------------

    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={
                "model": EMBED_MODEL,
                "input": text
            },
            timeout=60.0
        )

        if response.status_code == 200:

            data = response.json()

            embeddings = data.get("embeddings", [])

            if embeddings:

                vector = embeddings[0]

                if isinstance(vector, list) and vector:

                    print(
                        f"Embedding generated: "
                        f"{len(vector)} dimensions"
                    )

                    return vector

    except httpx.HTTPError:
        pass

    # --------------------------------------------------------
    # Legacy embedding endpoint
    # --------------------------------------------------------

    try:

        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={
                "model": EMBED_MODEL,
                "prompt": text
            },
            timeout=60.0
        )

        if response.status_code == 404:

            raise RuntimeError(
                f"Embedding model '{EMBED_MODEL}' "
                f"was not found in Ollama."
            )

        response.raise_for_status()

        data = response.json()

        vector = data.get("embedding", [])

        if not vector:

            raise RuntimeError(
                "Ollama returned an empty embedding."
            )

        print(
            f"Embedding generated: "
            f"{len(vector)} dimensions"
        )

        return vector

    except httpx.HTTPError as exc:

        raise RuntimeError(
            f"Failed to generate embedding using "
            f"'{EMBED_MODEL}'.\n"
            f"Error: {exc}"
        ) from exc


# ============================================================
# QDRANT COLLECTION CHECK
# ============================================================

async def check_collection(
    client: httpx.AsyncClient
) -> None:
    """Check whether the Qdrant collection exists."""

    url = (
        f"{QDRANT_URL}/collections/"
        f"{COLLECTION_NAME}"
    )

    try:

        response = await client.get(
            url,
            timeout=10.0
        )

        if response.status_code == 404:

            raise RuntimeError(
                f"Qdrant collection "
                f"'{COLLECTION_NAME}' does not exist."
            )

        response.raise_for_status()

        data = response.json()

        result = data.get("result", {})

        points_count = result.get(
            "points_count",
            "unknown"
        )

        vector_size = (
            result
            .get("config", {})
            .get("params", {})
            .get("vectors", {})
            .get("size", "unknown")
        )

        print(
            f"Qdrant collection: "
            f"{COLLECTION_NAME}"
        )

        print(
            f"Points: {points_count}"
        )

        print(
            f"Vector size: {vector_size}"
        )

    except httpx.HTTPError as exc:

        raise RuntimeError(
            f"Failed to inspect Qdrant collection "
            f"'{COLLECTION_NAME}'.\n"
            f"Error: {exc}"
        ) from exc


# ============================================================
# QDRANT SEARCH
# ============================================================

async def search_qdrant(
    client: httpx.AsyncClient,
    query_vector: List[float],
    limit: int = TOP_K
) -> List[str]:
    """
    Search Qdrant for similar vectors and extract
    text from payload.
    """

    search_url = (
        f"{QDRANT_URL}/collections/"
        f"{COLLECTION_NAME}/points/search"
    )

    try:

        response = await client.post(
            search_url,
            json={
                "vector": query_vector,
                "limit": limit,
                "with_payload": True
            },
            timeout=30.0
        )

        response.raise_for_status()

        data = response.json()

        results = data.get("result", [])

        print(
            f"Qdrant results returned: "
            f"{len(results)}"
        )

        contexts = []

        for item in results:

            payload = item.get(
                "payload",
                {}
            )

            score = item.get(
                "score",
                0
            )

            text_content = (
                payload.get("text")
                or payload.get("content")
                or payload.get("document")
                or payload.get("chunk")
            )

            if text_content:

                contexts.append(
                    str(text_content)
                )

                print(
                    f"Retrieved score: "
                    f"{score:.4f}"
                )

        return contexts

    except httpx.HTTPError as exc:

        raise RuntimeError(
            f"Qdrant search failed.\n"
            f"URL: {search_url}\n"
            f"Error: {exc}"
        ) from exc


# ============================================================
# LLM GENERATION
# ============================================================

async def generate_answer(
    client: httpx.AsyncClient,
    query: str,
    context: List[str]
) -> str:
    """Generate a grounded answer using Ollama."""

    if context:

        context_str = "\n".join(
            f"- {item}"
            for item in context
        )

    else:

        context_str = (
            "No relevant context was retrieved "
            "from the knowledge base."
        )

    prompt = f"""
You are a helpful RAG assistant.

Answer the user's question using ONLY the
provided context.

If the context does not contain enough information
to answer the question, clearly say that the
knowledge base does not contain enough information.

Do not invent facts.

Context:
{context_str}

Question:
{query}

Answer:
""".strip()

    try:

        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120.0
        )

        response.raise_for_status()

        data = response.json()

        answer = data.get(
            "response",
            ""
        ).strip()

        if not answer:

            raise RuntimeError(
                "Ollama returned an empty answer."
            )

        return answer

    except httpx.HTTPStatusError as exc:

        raise RuntimeError(
            f"Ollama generation failed.\n"
            f"HTTP status: "
            f"{exc.response.status_code}\n"
            f"Response: "
            f"{exc.response.text}"
        ) from exc

    except httpx.HTTPError as exc:

        raise RuntimeError(
            f"Could not communicate with Ollama.\n"
            f"Error: {exc}"
        ) from exc


# ============================================================
# COMPLETE QUERY PIPELINE
# ============================================================

async def run_query(
    user_query: str
) -> None:

    print()
    print("=" * 60)
    print("RAG QUERY")
    print("=" * 60)

    print(
        f"\nQuestion: '{user_query}'"
    )

    async with httpx.AsyncClient() as client:

        # ----------------------------------------------------
        # Step 0 — Infrastructure checks
        # ----------------------------------------------------

        print("\n[1/6] Checking Ollama...")

        await check_ollama(client)

        print("\n[2/6] Checking Qdrant...")

        await check_qdrant(client)

        print(
            f"\n[3/6] Checking collection "
            f"'{COLLECTION_NAME}'..."
        )

        await check_collection(client)

        # ----------------------------------------------------
        # Step 1 — Query embedding
        # ----------------------------------------------------

        print("\n[4/6] Embedding query...")

        query_vector = await get_embedding(
            client,
            user_query
        )

        if not query_vector:

            raise RuntimeError(
                "Query embedding is empty."
            )

        # ----------------------------------------------------
        # Step 2 — Vector search
        # ----------------------------------------------------

        print(
            "\n[5/6] Searching Qdrant vector DB..."
        )

        retrieved_texts = await search_qdrant(
            client,
            query_vector,
            limit=TOP_K
        )

        print(
            "\n--- Retrieved Context ---"
        )

        if retrieved_texts:

            for index, text in enumerate(
                retrieved_texts,
                start=1
            ):

                print(
                    f"\n[{index}] {text}"
                )

        else:

            print(
                "Warning: No matching context "
                "payload retrieved."
            )

        print(
            "\n------------------------"
        )

        # ----------------------------------------------------
        # Step 3 — LLM generation
        # ----------------------------------------------------

        print(
            "\n[6/6] Generating answer with Ollama..."
        )

        answer = await generate_answer(
            client,
            user_query,
            retrieved_texts
        )

        # ----------------------------------------------------
        # Final answer
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("ANSWER")
        print("=" * 60)

        print(answer)

        print()
        print("=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)


# ============================================================
# ERROR HANDLING / ENTRY POINT
# ============================================================

async def main() -> None:

    sample_question = (
        "What is RAG and how does it optimize LLMs?"
    )

    if len(sys.argv) > 1:

        sample_question = " ".join(
            sys.argv[1:]
        )

    try:

        await run_query(
            sample_question
        )

    except Exception as exc:

        print()
        print("=" * 60)
        print("PIPELINE ERROR")
        print("=" * 60)

        print(
            f"\n{type(exc).__name__}: {exc}"
        )

        print()


if __name__ == "__main__":

    asyncio.run(main())