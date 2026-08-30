import asyncio
import os
import sys
import httpx

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://agent_llm:11434")
QDRANT_URL = os.getenv("QDRANT_HOST", "http://agent_vector_db:6333")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
COLLECTION_NAME = "knowledge"

# Sample dataset
KNOWLEDGE_DATA = [
    "Machine learning is a subset of artificial intelligence that focuses on building systems that learn from data patterns.",

    "FastAPI is a modern, fast high-performance web framework for building APIs with Python 3.8+.",

    "Qdrant is a vector similarity search engine that provides a production-ready service with a convenient API to store vectors.",

    "Qdrant organizes data into collections containing points. Each point can contain a vector and optional payload metadata. Collections define the vector dimensionality and distance metric used for similarity search.",

    "Qdrant can store vectors in memory for fast access or use on-disk memory-mapped storage when configured with on_disk, providing a trade-off between search speed and RAM usage.",

    "Qdrant uses the HNSW graph index to enable fast approximate nearest-neighbor vector search. The HNSW index is an indexing structure used to efficiently traverse similar vectors; it is distinct from the underlying vector storage.",

    "Retrieval-Augmented Generation (RAG) optimizes LLM outputs by querying authoritative external knowledge bases before generating replies.",

    "Python asyncio is a library to write concurrent code using the async/await syntax.",

    "Vector embeddings are numerical representations of text that capture semantic meaning in high-dimensional space."
]


async def pull_model_if_missing(client: httpx.AsyncClient, model_name: str):
    """Automatically pulls the required Ollama model if it isn't locally available."""
    try:
        ollama_res = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        ollama_res.raise_for_status()
        models = [m.get("name", "") for m in ollama_res.json().get("models", [])]

        if not any(model_name in m for m in models):
            print(f"📥 Model '{model_name}' not found locally. Pulling model automatically...")
            pull_resp = await client.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=300.0  # Extended timeout for downloading
            )
            pull_resp.raise_for_status()
            print(f"✅ Successfully pulled '{model_name}'.")
    except Exception as e:
        print(f"⚠️ Unable to verify or pull model '{model_name}': {e}")


async def verify_services(client: httpx.AsyncClient):
    """Verify Ollama and Qdrant are online before proceeding."""
    print("Checking service health...")

    # Check Ollama
    try:
        ollama_res = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        ollama_res.raise_for_status()
    except Exception as e:
        print(f"❌ Could not connect to Ollama at {OLLAMA_URL}: {e}")
        sys.exit(1)

    # Check Qdrant
    try:
        qdrant_res = await client.get(f"{QDRANT_URL}/healthz", timeout=5.0)
        qdrant_res.raise_for_status()
    except Exception as e:
        print(f"❌ Could not connect to Qdrant at {QDRANT_URL}: {e}")
        sys.exit(1)

    print("✅ Ollama and Qdrant connections verified.")


async def get_embedding(client: httpx.AsyncClient, text: str) -> list[float]:
    """Fetch vector embedding from Ollama (/api/embed with fallback to /api/embeddings)."""
    # Try modern Ollama endpoint first
    try:
        resp = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=30.0
        )
        if resp.status_code == 200:
            embeddings = resp.json().get("embeddings", [])
            if embeddings:
                return embeddings[0]
    except httpx.HTTPError:
        pass

    # Fallback endpoint for older Ollama versions
    resp_legacy = await client.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=30.0
    )
    resp_legacy.raise_for_status()
    return resp_legacy.json().get("embedding", [])


async def setup_qdrant_collection(client: httpx.AsyncClient, vector_dim: int):
    """Re-creates the Qdrant collection matching the detected vector dimension."""
    col_url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}"

    # Check if collection exists and delete it for a clean slate
    col_check = await client.get(col_url)
    if col_check.status_code == 200:
        print(f"Collection '{COLLECTION_NAME}' exists. Re-creating...")
        await client.delete(col_url)

    # Create collection
    create_resp = await client.put(
        col_url,
        json={
            "vectors": {
                "size": vector_dim,
                "distance": "Cosine"
            }
        }
    )
    create_resp.raise_for_status()
    print(f"Created collection '{COLLECTION_NAME}' (dimension: {vector_dim}).")


async def run_ingestion():
    print("=== Automated Knowledge Ingestion ===")

    async with httpx.AsyncClient() as client:
        # Step 1: Health check & model check
        await verify_services(client)
        await pull_model_if_missing(client, EMBED_MODEL)

        # Step 2: Generate embeddings concurrently
        print(f"\nGenerating embeddings for {len(KNOWLEDGE_DATA)} items using '{EMBED_MODEL}'...")
        tasks = [get_embedding(client, text) for text in KNOWLEDGE_DATA]
        vectors = await asyncio.gather(*tasks)

        if not vectors or not vectors[0]:
            print("❌ Failed to generate vector embeddings.")
            return

        # Step 3: Configure Qdrant with auto-detected dimension size
        vector_dim = len(vectors[0])
        print(f"Detected vector dimension: {vector_dim}")
        await setup_qdrant_collection(client, vector_dim)

        # Step 4: Prepare batch payload
        points = [
            {
                "id": idx + 1,
                "vector": vector,
                "payload": {
                    "text": text,
                    "index": idx
                }
            }
            for idx, (text, vector) in enumerate(zip(KNOWLEDGE_DATA, vectors))
        ]

        # Step 5: Upsert points into Qdrant
        print("Uploading points to Qdrant...")
        upsert_resp = await client.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
            json={"points": points}
        )
        upsert_resp.raise_for_status()

        print(f"\n🎉 Successfully ingested {len(points)} documents into Qdrant!")


if __name__ == "__main__":
    asyncio.run(run_ingestion())