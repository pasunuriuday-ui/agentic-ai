import pytest

from app.services.query_decomposer import QueryDecomposer


def test_single_question():

    decomposer = QueryDecomposer()

    result = decomposer.decompose(
        "What is Qdrant?"
    )

    assert result == [
        "What is Qdrant?"
    ]


def test_two_questions():

    decomposer = QueryDecomposer()

    result = decomposer.decompose(
        "What is Qdrant and what is FastAPI?"
    )

    assert len(result) == 2
    assert result[0] == "What is Qdrant?"
    assert result[1].lower() == "what is fastapi?"


def test_three_questions():

    decomposer = QueryDecomposer()

    result = decomposer.decompose(
        "What is Qdrant? What is FastAPI? What is RAG?"
    )

    assert result == [
        "What is Qdrant?",
        "What is FastAPI?",
        "What is RAG?"
    ]


def test_compound_qdrant_mars_query():

    decomposer = QueryDecomposer()

    result = decomposer.decompose(
        "How does Qdrant handle vector storage and "
        "what is the capital of Mars?"
    )

    assert len(result) == 2

    assert "Qdrant" in result[0]
    assert "Mars" in result[1]


def test_empty_query():

    decomposer = QueryDecomposer()

    with pytest.raises(ValueError):

        decomposer.decompose("")