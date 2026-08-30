from app.services.retrieval_service import RetrievalService


def create_retriever() -> RetrievalService:
    """
    Create a clean retriever for every test.

    The production collection is persistent, so tests must
    explicitly clear the test collection before each test.
    """

    retriever = RetrievalService()

    try:
        retriever._client.delete_collection(
            collection_name=retriever._collection_name
        )
    except Exception:
        pass

    return RetrievalService()


def test_add_documents():
    retriever = create_retriever()

    docs = [
        {
            "text": (
                "Artificial intelligence is the simulation "
                "of human intelligence."
            )
        },
        {
            "text": "Machine learning is a subset of AI."
        },
        {
            "text": "Deep learning uses neural networks."
        },
    ]

    count = retriever.add_documents(docs)

    assert count == 3
    assert retriever.count() == 3


def test_search_returns_results():
    retriever = create_retriever()

    docs = [
        {
            "text": (
                "Artificial intelligence is the simulation "
                "of human intelligence."
            )
        },
        {
            "text": "Machine learning is a subset of AI."
        },
        {
            "text": "Deep learning uses neural networks."
        },
    ]

    retriever.add_documents(docs)

    results = retriever.search("What is AI?")

    assert results
    assert len(results) <= 3


def test_search_returns_document_payload():
    retriever = create_retriever()

    docs = [
        {
            "text": (
                "Artificial intelligence is the simulation "
                "of human intelligence."
            )
        },
        {
            "text": "Machine learning is a subset of AI."
        },
        {
            "text": "Deep learning uses neural networks."
        },
    ]

    retriever.add_documents(docs)

    results = retriever.search(
        "What is artificial intelligence?"
    )

    assert results
    assert all(
        "text" in result
        for result in results
    )


def test_search_returns_scores():
    retriever = create_retriever()

    docs = [
        {
            "text": (
                "Artificial intelligence is the simulation "
                "of human intelligence."
            )
        },
        {
            "text": "Machine learning is a subset of AI."
        },
        {
            "text": "Deep learning uses neural networks."
        },
    ]

    retriever.add_documents(docs)

    results = retriever.search(
        "What is artificial intelligence?"
    )

    assert results

    for result in results:
        assert "_score" in result
        assert result["_score"] is not None
        assert isinstance(
            result["_score"],
            (int, float),
        )


def test_empty_documents_rejected():
    retriever = create_retriever()

    try:
        retriever.add_documents([])

        assert False, "Expected ValueError"

    except ValueError as exc:
        assert (
            "Documents list cannot be empty"
            in str(exc)
        )


def test_empty_query_rejected():
    retriever = create_retriever()

    try:
        retriever.search("")

        assert False, "Expected ValueError"

    except ValueError as exc:
        assert (
            "Query cannot be empty"
            in str(exc)
        )