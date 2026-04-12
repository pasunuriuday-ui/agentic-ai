import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from app.agents.state_machine_agent import StateMachineAgent
from app.models.api_models import QueryRequest, QueryResponse
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService
from app.tools.rag_tool import RAGTool


# --- Configuration ---
DEFAULT_DOCUMENTS: List[Dict[str, str]] = [
    {"text": "Artificial intelligence is the simulation of human intelligence."},
    {"text": "Machine learning is a subset of AI."},
    {"text": "Deep learning uses neural networks."},
]


# --- Application State ---
class AppState:
    agent: StateMachineAgent
    llm: LLMService
    retrieval: RetrievalService


state = AppState()


# --- Logging ---
def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


# --- Initialization ---
def initialize_services() -> None:
    logger = logging.getLogger(__name__)
    logger.info("Initializing services...")

    state.llm = LLMService()
    state.retrieval = RetrievalService()

    state.retrieval.add_documents(DEFAULT_DOCUMENTS)
    logger.info(f"Indexed {len(DEFAULT_DOCUMENTS)} documents")

    tools = {
        "search_docs": RAGTool(state.retrieval)
    }

    state.agent = StateMachineAgent(state.llm, tools)

    logger.info("Services initialized successfully")


# --- Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()

    try:
        initialize_services()
        yield
    except Exception as e:
        logging.critical(f"Startup failed: {e}", exc_info=True)
        raise RuntimeError(f"Failed to start application: {e}") from e


# --- App ---
app = FastAPI(
    title="Agentic AI API",
    description="State Machine Agentic AI with RAG",
    version="2.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)


# --- Global Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    logging.exception("Unhandled exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=QueryResponse(
            success=False,
            error="Internal server error"
        ).model_dump(exclude={"answer"})
    )


# --- Routes ---
@app.get("/", response_model=Dict[str, str])
async def root() -> Dict[str, str]:
    return {
        "message": "Agentic AI API running",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=Dict[str, str])
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK
)
async def query_api(request: QueryRequest):
    try:
        result = state.agent.run(request.query)

        # ❌ Error case
        if not result.success:
            return JSONResponse(
                status_code=200,
                content=QueryResponse(
                    success=False,
                    error="No relevant information found."
                ).model_dump(exclude={"answer"})
            )

        # ✅ Success case (NO CHANGE)
        return QueryResponse(
            success=True,
            answer=result.answer
        )

    except Exception as e:
        logging.exception("Query processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)  #  keep debug visibility
        )


# --- Utility (UNCHANGED) ---
def _is_error_result(result: str) -> bool:
    if not result:
        return True

    error_indicators = [
        "query cannot be empty",
        "unable to generate",
        "system error",
        "failed to complete",
        "no relevant information"
    ]

    return any(indicator in result.lower() for indicator in error_indicators)