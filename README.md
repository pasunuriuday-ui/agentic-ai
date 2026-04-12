# Agentic AI System (RAG + State Machine)

Built to demonstrate production-grade Agentic AI with controlled reasoning and zero hallucination.

This project is a production-style Agentic AI system designed to answer questions using a structured, reliable pipeline instead of direct LLM responses.

The goal of this system is to avoid hallucinations, ensure deterministic behavior, and demonstrate how modern AI applications are built in real-world engineering environments.

---

## What This Project Does

Given a user query, the system performs the following steps:

- Decides whether external knowledge is required  
- Retrieves relevant documents using semantic search (RAG)  
- Validates the retrieved information  
- Generates a final answer using an LLM (Ollama)  

If no relevant information is found, the system safely refuses to answer instead of guessing.

---

## Architecture Overview

The system is implemented using a state machine-based agent rather than a simple prompt-based approach.

Flow:

User Query  
→ Planner (decides tool usage)  
→ Executor (retrieves documents)  
→ Validator (ensures correctness)  
→ Synthesizer (generates final answer)  
→ API Response  

This design ensures modularity, observability, and reliability.

---

## Tech Stack

- FastAPI – Backend API  
- Ollama (LLaMA 3) – Local LLM  
- Qdrant / Vector Search – Semantic retrieval  
- Python – Core implementation  

---

## Key Features

- Retrieval-Augmented Generation (RAG)  
- State machine-based agent architecture  
- Strict validation to prevent hallucination  
- Deterministic and reliable outputs  
- Modular and extensible design  
- Clean API for integration  

---

## Example

### Input
```json
{
  "query": "What is machine learning?"
}
```

### Output
```json
{
  "success": true,
  "answer": "Machine learning is a subset of AI."
}
```

---

## Safety Behavior

```json
{
  "success": false,
  "error": "No relevant information found."
}
```

This behavior is intentional and ensures reliability in real-world scenarios.
