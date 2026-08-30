import os
import re
from typing import Optional

import httpx
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import settings
from app.services.file_ingestion_service import FileIngestionService
from app.services.query_decomposer import QueryDecomposer


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = settings.ollama_host.rstrip("/")

QDRANT_URL = settings.qdrant_host.rstrip("/")

EMBED_MODEL = settings.embedding_model

LLM_MODEL = settings.llm_model

COLLECTION_NAME = settings.collection_name

TOP_K = int(
    os.getenv("TOP_K", "3")
)

# Minimum Qdrant similarity score required
# before the LLM is allowed to generate an answer.
MIN_RETRIEVAL_SCORE = float(
    os.getenv("MIN_RETRIEVAL_SCORE", "0.70")
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Production Agentic RAG System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# FILE INGESTION SERVICE
# ============================================================

file_ingestion = FileIngestionService(
    ollama_url=OLLAMA_URL,
    qdrant_url=QDRANT_URL,
    embed_model=EMBED_MODEL,
    collection_name=COLLECTION_NAME,
)

query_decomposer = QueryDecomposer()


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

        # ----------------------------------------------------
        # Query decomposition
        # ----------------------------------------------------

        self.sub_queries: list[str] = []

        # ----------------------------------------------------
        # Original single-query fields
        # ----------------------------------------------------

        self.query_vector: list[float] = []

        self.documents: list[str] = []

        self.scores: list[float] = []

        # ----------------------------------------------------
        # Per-sub-query retrieval
        # ----------------------------------------------------

        self.sub_query_documents: list[list[str]] = []

        self.sub_query_scores: list[list[float]] = []

        self.sub_query_vectors: list[list[float]] = []

        # ----------------------------------------------------
        # Validation / final result
        # ----------------------------------------------------

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
    knowledge retrieval and decompose
    compound queries into independent
    sub-queries.
    """

    if not state.query or not state.query.strip():

        state.error = (
            "Query cannot be empty."
        )

        state.requires_tools = False

        return state

    try:

        state.sub_queries = (
            query_decomposer.decompose(
                state.query
            )
        )

        if not state.sub_queries:

            state.error = (
                "No valid query detected."
            )

            state.requires_tools = False

            return state

        state.requires_tools = True

    except ValueError as exc:

        state.error = str(exc)

        state.requires_tools = False

    except Exception as exc:

        state.error = (
            f"Query decomposition error: {exc}"
        )

        state.requires_tools = False

    return state


# ============================================================
# EXECUTOR
# ============================================================

async def executor_node(
    state: AgentState
) -> AgentState:

    """
    Generate embeddings and retrieve relevant
    documents from Qdrant independently for
    every sub-query.
    """

    if not state.requires_tools:

        return state

    if not state.sub_queries:

        state.error = (
            "No sub-queries available for retrieval."
        )

        return state

    try:

        async with httpx.AsyncClient() as client:

            # ------------------------------------------------
            # Process every sub-query independently
            # ------------------------------------------------

            for sub_query in state.sub_queries:

                documents_for_query: list[str] = []

                scores_for_query: list[float] = []

                # --------------------------------------------
                # Generate embedding
                # --------------------------------------------

                embedding_response = await client.post(

                    f"{OLLAMA_URL}/api/embed",

                    json={
                        "model": EMBED_MODEL,
                        "input": sub_query
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

                query_vector = embeddings[0]

                state.sub_query_vectors.append(
                    query_vector
                )

                # Keep original field populated
                # for compatibility.
                if not state.query_vector:

                    state.query_vector = query_vector

                # --------------------------------------------
                # Search Qdrant
                # --------------------------------------------

                search_url = (
                    f"{QDRANT_URL}/collections/"
                    f"{COLLECTION_NAME}/points/search"
                )

                qdrant_response = await client.post(

                    search_url,

                    json={
                        "vector": query_vector,
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

                # --------------------------------------------
                # Extract documents
                # --------------------------------------------

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

                        document = str(text)

                        score = float(
                            result.get(
                                "score",
                                0.0
                            )
                        )

                        documents_for_query.append(
                            document
                        )

                        scores_for_query.append(
                            score
                        )

                        # ------------------------------------------------
                        # Retrieval diagnostics
                        # ------------------------------------------------

                        print("SUB-QUERY:", sub_query)
                        print("RETRIEVAL SCORES:", scores_for_query)
                        print("RETRIEVED DOCUMENTS:")

                        for retrieved_document in documents_for_query:
                            print("-----")
                            print(retrieved_document)

                        # Preserve existing aggregate fields.
                        state.documents.append(
                            document
                        )

                        state.scores.append(
                            score
                        )

                # --------------------------------------------
                # Save independent retrieval result
                # --------------------------------------------

                state.sub_query_documents.append(
                    documents_for_query
                )

                state.sub_query_scores.append(
                    scores_for_query
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
# CONTEXT SUPPORT CHECK
# ============================================================

_CONTEXT_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can",
    "could", "does", "do", "for", "from", "how", "i", "in",
    "is", "it", "me", "of", "on", "or", "please", "tell",
    "that", "the", "this", "to", "what", "when", "where",
    "which", "who", "why", "with", "would", "you", "your",
    "according", "provided", "uploaded", "pdf", "document",
    "information", "method", "preparation", "recipe",
    "ingredients", "ingredient", "listed", "list", "give",
    "explain", "describe", "contain", "contains",
}


def _normalize_context_terms(text: str) -> set[str]:
    """
    Convert text into meaningful normalized terms.

    This is a deterministic safety check only. Qdrant remains
    responsible for semantic retrieval.
    """

    words = re.findall(
        r"[a-zA-Z0-9]+",
        text.lower(),
    )

    terms: set[str] = set()

    for word in words:

        if len(word) < 3:
            continue

        if word in _CONTEXT_STOP_WORDS:
            continue

        # Small normalization for common English endings.
        normalized = word

        for suffix in (
            "ing",
            "ed",
            "es",
            "s",
        ):
            if (
                normalized.endswith(suffix)
                and len(normalized) - len(suffix) >= 4
            ):
                normalized = normalized[
                    :-len(suffix)
                ]
                break

        if len(normalized) >= 3:
            terms.add(normalized)

    return terms


def context_supports_query(
    sub_query: str,
    documents: list[str],
) -> bool:
    """
    Deterministic context-support safety gate.

    The retrieved context must contain meaningful terms
    related to the sub-query. This prevents a semantically
    similar but unsupported retrieval result from being
    passed to the LLM as if it contained the answer.
    """

    query_terms = _normalize_context_terms(
        sub_query
    )

    context_terms = _normalize_context_terms(
        "\n".join(documents)
    )

    if not query_terms or not context_terms:
        return False

    overlap = query_terms & context_terms

    # A distinctive topic/entity term is normally enough
    # when the retrieved context explicitly contains it.
    if len(overlap) >= 1:
        return True

    return False


# ============================================================
# VALIDATOR
# ============================================================

async def validator_node(
    state: AgentState
) -> AgentState:

    """
    Validate every independent sub-query.

    A compound query is accepted only when every
    sub-query has relevant retrieved context
    above the configured confidence threshold.
    """

    if state.error:

        state.is_valid = False

        return state

    if not state.sub_queries:

        state.is_valid = False

        state.error = (
            "No sub-queries available."
        )

        return state

    if not state.sub_query_scores:

        state.is_valid = False

        state.error = (
            "No retrieval confidence available."
        )

        return state

    # --------------------------------------------------------
    # Strict per-sub-query retrieval confidence check
    # --------------------------------------------------------

    for index, sub_query in enumerate(
        state.sub_queries
    ):

        # Ensure every sub-query has a corresponding
        # retrieval result.
        if index >= len(
            state.sub_query_scores
        ):

            state.is_valid = False

            state.error = (
                "No relevant information found "
                f"for sub-query: {sub_query}"
            )

            return state

        scores = (
            state.sub_query_scores[index]
        )

        documents = (
            state.sub_query_documents[index]
        )

        # ----------------------------------------------------
        # No documents
        # ----------------------------------------------------

        if not documents:

            state.is_valid = False

            state.error = (
                "No relevant information found "
                f"for sub-query: {sub_query}"
            )

            return state

        # ----------------------------------------------------
        # No scores
        # ----------------------------------------------------

        if not scores:

            state.is_valid = False

            state.error = (
                "No retrieval confidence available "
                f"for sub-query: {sub_query}"
            )

            return state

        # ----------------------------------------------------
        # Best score for THIS sub-query
        # ----------------------------------------------------

        best_score = max(scores)

        if best_score < MIN_RETRIEVAL_SCORE:

            state.is_valid = False

            state.error = (
                "No relevant information found."
            )

            return state

        # ----------------------------------------------------
        # Context-support safety gate
        # ----------------------------------------------------

        if not context_supports_query(
            sub_query,
            documents,
        ):

            state.is_valid = False

            state.error = (
                "No relevant information found "
                f"for sub-query: {sub_query}"
            )

            return state

    # --------------------------------------------------------
    # Every sub-query passed
    # --------------------------------------------------------

    state.is_valid = True

    return state


# ============================================================
# SYNTHESIZER
# ============================================================

async def synthesizer_node(
    state: AgentState
) -> AgentState:

    """
    Generate an answer using only the context
    retrieved for every validated sub-query.
    """

    if not state.is_valid:

        return state

    # --------------------------------------------------------
    # Build structured context
    # --------------------------------------------------------

    context_sections: list[str] = []

    for index, sub_query in enumerate(
        state.sub_queries
    ):

        documents = (
            state.sub_query_documents[index]
        )

        section = "\n".join(

            f"- {document}"

            for document in documents

        )

        context_sections.append(

            f"""
Sub-query {index + 1}:
{sub_query}

Retrieved context:
{section}
""".strip()

        )

    context = "\n\n".join(
        context_sections
    )

    prompt = f"""
You are a strict grounded Retrieval-Augmented Generation assistant.

Use ONLY the information contained in the retrieved context.

The user query may contain multiple independent questions.

Every sub-query has already passed an independent
retrieval relevance check.

Rules:

1. Answer ONLY from the provided retrieved context.
2. Do not use outside knowledge.
3. Do not invent facts.
4. Do not assume information that is not present.
5. Keep each answer grounded in its corresponding sub-query context.
6. If information required to answer a part is not present,
   say that the information is not available in the provided context.
7. Do not fabricate an answer.
8. Treat the RETRIEVED CONTEXT as the only authoritative source for the answer.
9. If the retrieved context contains the requested information, answer the
   question directly using that information. Do not refuse merely because
   the model's prior knowledge differs from or cannot confirm the context.
10. Never use pretrained knowledge, general knowledge, common recipes,
    assumptions, or outside sources to add information that is not supported
    by the retrieved context.
11. If the retrieved context does not contain enough information to answer
    the user's question, output EXACTLY:
    INSUFFICIENT_CONTEXT
12. Do not recommend websites, books, searches, or alternative sources.
13. Do not claim that information is absent from the document when the
    retrieved context explicitly contains that information.
14. If the requested entity, topic, ingredient, method, fact, or other
    information is explicitly supported by the retrieved context, answer it
    from that context.

Retrieved context:

{context}

Original user question:

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
                    "stream": False,
                    "options": {
                        "temperature": 0
                    }
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
                or answer.strip().upper()
                == "INSUFFICIENT_CONTEXT"
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
# FILE UPLOAD
# ============================================================

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...)
):

    filename = file.filename or ""

    extension = os.path.splitext(
        filename
    )[1].lower()

    # --------------------------------------------------------
    # Supported file types
    # --------------------------------------------------------

    if extension not in {
        ".pdf",
        ".txt",
    }:

        return {

            "success": False,

            "error": (
                "Unsupported file type. "
                "Only PDF and TXT files are supported."
            )

        }

    # --------------------------------------------------------
    # Read file
    # --------------------------------------------------------

    content = await file.read()

    if not content:

        return {

            "success": False,

            "error": "Uploaded file is empty."

        }

    # --------------------------------------------------------
    # Ingest
    # --------------------------------------------------------

    try:

        result = await file_ingestion.ingest(
            filename,
            content,
        )

        return result

    except Exception as exc:

        return {

            "success": False,

            "error": (
                f"File ingestion failed: {exc}"
            )

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
    # Planner / Query Decomposition
    # --------------------------------------------------------

    state = await planner_node(
        state
    )

    if state.error:

        return {

            "success": False,

            "error": state.error

        }

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