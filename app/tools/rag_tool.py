import logging
from typing import Any, Dict, List, Protocol

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)


class RetrievalServiceProtocol(Protocol):
    def search(self, query: str) -> List[Dict[str, Any]]:
        ...


class RAGTool(BaseTool):
    """
    Retrieval-Augmented Generation tool for document search.
    """

    name: str = "search_docs"
    DEFAULT_DESCRIPTION: str = "Search for relevant documents using semantic similarity"

    def __init__(self, retrieval_service: RetrievalServiceProtocol) -> None:
        self._retriever = retrieval_service
        self._description = self.DEFAULT_DESCRIPTION

    @property
    def description(self) -> str:
        return self._description

    def run(self, query: str) -> str:
        if not query or not query.strip():
            logger.warning("RAGTool received empty query")
            return "No search query provided."

        try:
            print("TOOL USED")  # 🔥 AGENTIC PROOF
            results = self._retriever.search(query.strip())

            # ✅ FIX: limit to TOP 1 result (precision improvement)
            results = results[:1]

        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return "Document search unavailable."

        if not results:
            logger.info(f"No documents found for query: {query[:50]}...")
            return "No relevant documents found."

        return self._format_results(results)

    def _format_results(self, results: List[Dict[str, Any]]) -> str:
        texts: List[str] = []

        for i, result in enumerate(results):
            if not isinstance(result, dict):
                continue

            text = result.get("text")
            if not text:
                continue

            texts.append(str(text).strip())

        if not texts:
            return "Retrieved documents had no readable content."

        return "\n\n".join(texts)