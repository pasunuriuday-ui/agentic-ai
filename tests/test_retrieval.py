from app.services.retrieval_service import RetrievalService


def create_retriever() -> RetrievalService:
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

    results = retriever.search("What is artificial intelligence?")

    assert results
    assert all("text" in result for result in results)


def test_empty_documents_rejected():
    retriever = create_retriever()

    try:
        retriever.add_documents([])
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Documents list cannot be empty" in str(exc)


def test_empty_query_rejected():
    retriever = create_retriever()

    try:
        retriever.search("")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Query cannot be empty" in str(exc)