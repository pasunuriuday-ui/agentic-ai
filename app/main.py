import os
from typing import Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_HOST",
    "http://ollama:11434"
).rstrip("/")

QDRANT_URL = os.getenv(
    "QDRANT_HOST",
    "http://qdrant:6333"
).rstrip("/")

EMBED_MODEL = os.getenv(
    "EMBED_MODEL",
    "nomic-embed-text"
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "llama3"
)

COLLECTION_NAME = os.getenv(
    "COLLECTION_NAME",
    "knowledge"
)

TOP_K = int(
    os.getenv("TOP_K", "3")
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Production Agentic RAG System",
    version="1.0.0"
)


# ============================================================
# API MODELS
# ============================================================

class QueryRequest(BaseModel):
    query: str


# ============================================================
# AGENT STATE
# ============================================================

class AgentState:

    def __init__(self, query: str):

        self.query: str = query

        self.requires_tools: bool = False

        self.query_vector: list[float] = []

        self.documents: list[str] = []

        self.scores: list[float] = []

        self.is_valid: bool = False

        self.final_answer: Optional[str] = None

        self.error: Optional[str] = None


# ============================================================
# PLANNER
# ============================================================

async def planner_node(
    state: AgentState
) -> AgentState:

    """
    Decide whether the query requires
    knowledge retrieval.
    """

    state.requires_tools = True

    return state


# ============================================================
# EXECUTOR
# ============================================================

async def executor_node(
    state: AgentState
) -> AgentState:

    """
    Generate query embedding and retrieve
    relevant documents from Qdrant.
    """

    if not state.requires_tools:

        return state

    try:

        async with httpx.AsyncClient() as client:

            # ------------------------------------------------
            # Generate embedding
            # ------------------------------------------------

            embedding_response = await client.post(

                f"{OLLAMA_URL}/api/embed",

                json={
                    "model": EMBED_MODEL,
                    "input": state.query
                },

                timeout=60.0
            )

            embedding_response.raise_for_status()

            embedding_data = (
                embedding_response.json()
            )

            embeddings = embedding_data.get(
                "embeddings",
                []
            )

            if not embeddings:

                state.error = (
                    "Embedding generation returned "
                    "no vector."
                )

                return state

            state.query_vector = embeddings[0]

            # ------------------------------------------------
            # Search Qdrant
            # ------------------------------------------------

            search_url = (
                f"{QDRANT_URL}/collections/"
                f"{COLLECTION_NAME}/points/search"
            )

            qdrant_response = await client.post(

                search_url,

                json={
                    "vector": state.query_vector,
                    "limit": TOP_K,
                    "with_payload": True
                },

                timeout=30.0
            )

            qdrant_response.raise_for_status()

            results = (
                qdrant_response
                .json()
                .get("result", [])
            )

            # ------------------------------------------------
            # Extract documents
            # ------------------------------------------------

            for result in results:

                payload = result.get(
                    "payload",
                    {}
                )

                text = (
                    payload.get("text")
                    or payload.get("content")
                    or payload.get("document")
                    or payload.get("chunk")
                )

                if text:

                    state.documents.append(
                        str(text)
                    )

                    state.scores.append(
                        float(
                            result.get(
                                "score",
                                0.0
                            )
                        )
                    )

    except httpx.HTTPError as exc:

        state.error = (
            f"Retrieval service error: {exc}"
        )

    except Exception as exc:

        state.error = (
            f"Executor error: {exc}"
        )

    return state


# ============================================================
# VALIDATOR
# ============================================================

async def validator_node(
    state: AgentState
) -> AgentState:

    """
    Ensure usable context was retrieved.
    """

    if state.error:

        state.is_valid = False

        return state

    if not state.documents:

        state.is_valid = False

        state.error = (
            "No relevant information found."
        )

        return state

    state.is_valid = True

    return state


# ============================================================
# SYNTHESIZER
# ============================================================

async def synthesizer_node(
    state: AgentState
) -> AgentState:

    """
    Generate an answer using only
    retrieved context.
    """

    if not state.is_valid:

        return state

    context = "\n".join(

        f"- {document}"

        for document in state.documents

    )

    prompt = f"""
You are a grounded Retrieval-Augmented Generation assistant.

Use ONLY the information contained in the context.

Rules:

1. Do not use outside knowledge.
2. Do not invent facts.
3. Do not assume information that is not present.
4. If the context does not contain enough information,
   respond exactly:

No relevant information found.

Context:
{context}

Question:
{state.query}

Answer:
""".strip()

    try:

        async with httpx.AsyncClient() as client:

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

                state.is_valid = False

                state.error = (
                    "LLM returned an empty response."
                )

                return state

            if (
                answer.lower()
                == "no relevant information found."
            ):

                state.is_valid = False

                state.error = (
                    "No relevant information found."
                )

                return state

            state.final_answer = answer

    except httpx.HTTPError as exc:

        state.is_valid = False

        state.error = (
            f"LLM communication error: {exc}"
        )

    except Exception as exc:

        state.is_valid = False

        state.error = (
            f"Synthesizer error: {exc}"
        )

    return state


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {

        "service":
            "Production Agentic RAG System",

        "status":
            "running"

    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    ollama_status = "unknown"

    qdrant_status = "unknown"

    async with httpx.AsyncClient() as client:

        # ----------------------------------------------------
        # Ollama
        # ----------------------------------------------------

        try:

            response = await client.get(

                f"{OLLAMA_URL}/api/tags",

                timeout=5.0

            )

            response.raise_for_status()

            models = [

                model.get(
                    "name",
                    ""
                )

                for model
                in response
                .json()
                .get(
                    "models",
                    []
                )
            ]

            ollama_status = (
                "healthy"
                if any(
                    LLM_MODEL in model
                    for model in models
                )
                else "model_missing"
            )

        except Exception:

            ollama_status = "unavailable"

        # ----------------------------------------------------
        # Qdrant
        # ----------------------------------------------------

        try:

            response = await client.get(

                f"{QDRANT_URL}/collections",

                timeout=5.0

            )

            response.raise_for_status()

            qdrant_status = "healthy"

        except Exception:

            qdrant_status = "unavailable"

    return {

        "status": "healthy",

        "ollama": ollama_status,

        "qdrant": qdrant_status,

        "embedding_model": EMBED_MODEL,

        "llm_model": LLM_MODEL,

        "collection": COLLECTION_NAME

    }


# ============================================================
# QUERY ENDPOINT
# ============================================================

@app.post("/query")
async def execute_agent_pipeline(
    request: QueryRequest
):

    state = AgentState(
        query=request.query
    )

    # --------------------------------------------------------
    # Planner
    # --------------------------------------------------------

    state = await planner_node(
        state
    )

    # --------------------------------------------------------
    # Executor
    # --------------------------------------------------------

    state = await executor_node(
        state
    )

    if state.error:

        return {

            "success": False,

            "error": state.error

        }

    # --------------------------------------------------------
    # Validator
    # --------------------------------------------------------

    state = await validator_node(
        state
    )

    if not state.is_valid:

        return {

            "success": False,

            "error": state.error

        }

    # --------------------------------------------------------
    # Synthesizer
    # --------------------------------------------------------

    state = await synthesizer_node(
        state
    )

    if not state.is_valid:

        return {

            "success": False,

            "error": state.error

        }

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        "success": True,

        "answer": state.final_answer,

        "retrieved_documents":
            len(state.documents),

        "retrieval_scores":
            state.scores

    }