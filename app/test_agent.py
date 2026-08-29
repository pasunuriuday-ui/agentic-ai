"""
Integration tests for the Production Agentic RAG System.

These tests use the real FastAPI application and therefore exercise:

FastAPI
   ↓
Planner
   ↓
Ollama embedding
   ↓
Qdrant retrieval
   ↓
Validator
   ↓
Ollama LLM
   ↓
API response

Requirements:
    pytest
    pytest-asyncio  # not required with TestClient
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ============================================================
# TEST CLIENT
# ============================================================

client = TestClient(app)


# ============================================================
# EXPECTED CONFIGURATION
# ============================================================

COLLECTION_NAME = "knowledge"
EXPECTED_EMBEDDING_MODEL = "nomic-embed-text"
EXPECTED_LLM_MODEL = "llama3:latest"


# ============================================================
# TEST 1 — ROOT ENDPOINT
# ============================================================

def test_root_endpoint():

    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["service"] == (
        "Production Agentic RAG System"
    )

    assert data["status"] == "running"


# ============================================================
# TEST 2 — HEALTH ENDPOINT
# ============================================================

def test_health_endpoint():

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"

    assert data["ollama"] == "healthy"

    assert data["qdrant"] == "healthy"

    assert data["embedding_model"] == (
        EXPECTED_EMBEDDING_MODEL
    )

    assert data["llm_model"] == (
        EXPECTED_LLM_MODEL
    )

    assert data["collection"] == (
        COLLECTION_NAME
    )


# ============================================================
# TEST 3 — HAPPY PATH / RAG
# ============================================================

def test_known_question_returns_grounded_answer():

    response = client.post(
        "/query",
        json={
            "query": (
                "How does Qdrant store vectors?"
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    # API contract
    assert data["success"] is True

    # Answer must exist
    assert isinstance(
        data["answer"],
        str,
    )

    assert len(
        data["answer"].strip()
    ) > 0

    # Retrieval must actually happen
    assert data["retrieved_documents"] > 0

    # Scores must be returned
    assert len(
        data["retrieval_scores"]
    ) > 0

    # Every score must be numeric
    for score in data["retrieval_scores"]:

        assert isinstance(
            score,
            (int, float),
        )


# ============================================================
# TEST 4 — REFUSAL / UNKNOWN QUESTION
# ============================================================

def test_unknown_question_is_rejected():

    response = client.post(
        "/query",
        json={
            "query": (
                "What is the capital of Mars "
                "and who is its president?"
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    # Must refuse
    assert data["success"] is False

    # Must return safety error
    assert data["error"] == (
        "No relevant information found."
    )


# ============================================================
# TEST 5 — EMPTY QUERY
# ============================================================

def test_empty_query():

    response = client.post(
        "/query",
        json={
            "query": ""
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False


# ============================================================
# TEST 6 — NORMAL UNRELATED QUESTION
# ============================================================

def test_unrelated_question_is_rejected():

    response = client.post(
        "/query",
        json={
            "query": (
                "Who won the football match "
                "yesterday?"
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False

    assert data["error"] == (
        "No relevant information found."
    )


# ============================================================
# TEST 7 — RESPONSE CONTRACT
# ============================================================

def test_success_response_contract():

    response = client.post(
        "/query",
        json={
            "query": (
                "What is machine learning?"
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    if data["success"]:

        assert "answer" in data

        assert "retrieved_documents" in data

        assert "retrieval_scores" in data

        assert isinstance(
            data["retrieved_documents"],
            int,
        )

        assert isinstance(
            data["retrieval_scores"],
            list,
        )

    else:

        assert "error" in data


# ============================================================
# TEST 8 — NO HALLUCINATION CONTRACT
# ============================================================

def test_unknown_query_never_returns_success():

    unknown_queries = [

        "What is the capital of Mars?",

        "Who is the president of Jupiter?",

        "What is the population of the Moon?",

    ]

    for query in unknown_queries:

        response = client.post(
            "/query",
            json={
                "query": query
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["success"] is False

        assert data["error"] == (
            "No relevant information found."
        )