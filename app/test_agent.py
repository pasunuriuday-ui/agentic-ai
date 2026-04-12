from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService
from app.agents.orchestrator import Orchestrator
from app.agents.agent import Agent
from app.tools.rag_tool import RAGTool


def build_agent() -> Agent:
    llm = LLMService()
    retrieval = RetrievalService()

    docs = [
        {"text": "Artificial intelligence is the simulation of human intelligence."},
        {"text": "Machine learning is a subset of AI."},
        {"text": "Deep learning uses neural networks."},
    ]

    retrieval.add_documents(docs)

    tools = {
        "search_docs": RAGTool(retrieval)
    }

    orchestrator = Orchestrator(llm, tools)

    return Agent(orchestrator)


def main():
    agent = build_agent()

    query = "What is artificial intelligence?"

    result = agent.run(query)

    print("\nFINAL RESULT:\n")
    print(result)


if __name__ == "__main__":
    main()