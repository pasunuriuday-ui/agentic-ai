from app.services.retrieval_service import RetrievalService

retriever = RetrievalService()

docs = [
    {"text": "Artificial intelligence is the simulation of human intelligence."},
    {"text": "Machine learning is a subset of AI."},
    {"text": "Deep learning uses neural networks."},
]

retriever.add_documents(docs)

results = retriever.search("What is AI?")

print("RESULTS:")
for r in results:
    print(r)