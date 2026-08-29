import os
import pytest

from app.services.llm_service import LLMService


OLLAMA_URL = os.getenv(
    "OLLAMA_HOST",
    "http://agent_llm:11434",
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "llama3:latest",
)


@pytest.mark.integration
def test_llm_health():

    llm = LLMService(
        base_url=OLLAMA_URL,
        model=LLM_MODEL,
    )

    assert llm.health_check() is True


@pytest.mark.integration
def test_llm_generate():

    llm = LLMService(
        base_url=OLLAMA_URL,
        model=LLM_MODEL,
        timeout=120,
    )

    response = llm.generate(
        "What is artificial intelligence?"
    )

    assert isinstance(response, str)
    assert len(response.strip()) > 0


def test_llm_rejects_empty_prompt():

    llm = LLMService(
        base_url=OLLAMA_URL,
        model=LLM_MODEL,
    )

    try:
        llm.generate("")

        assert False, (
            "Expected ValueError for empty prompt"
        )

    except ValueError as exc:
        assert str(exc) == "Prompt cannot be empty"