import logging
from typing import Any, Optional, Protocol

from app.agents.verifier import Verifier
from app.core.config import settings

logger = logging.getLogger(__name__)


class OrchestratorProtocol(Protocol):
    """Interface for reasoning orchestrators."""
    
    def run(self, query: str, max_steps: int) -> str:
        """Execute reasoning loop and return raw output."""
        ...


class Agent:
    """
    High-level agent controller coordinating reasoning and verification.
    
    Orchestrates the end-to-end flow: query validation -> reasoning -> 
    verification -> cleaned answer delivery.
    """
    
    ERROR_EMPTY_QUERY: str = "Query cannot be empty."
    ERROR_NO_OUTPUT: str = "Unable to generate reliable answer."
    ERROR_SYSTEM: str = "System error. Please try again."
    
    def __init__(
        self, 
        orchestrator: OrchestratorProtocol, 
        llm: Optional[Any] = None
    ) -> None:
        """
        Initialize the Agent.
        
        Args:
            orchestrator: Handles multi-step reasoning and tool execution
            llm: Language model (unused, kept for backward compatibility)
        """
        self._orchestrator = orchestrator
        self._verifier = Verifier()
        self._llm = llm  # Stored but not utilized by this implementation
        
        logger.debug("Agent initialized")
    
    def run(self, query: Optional[str]) -> str:
        """
        Execute the complete agent pipeline.
        
        Args:
            query: User's question or task. None or whitespace-only 
                   returns error message.
            
        Returns:
            Clean, verified answer or error message string.
        """
        # Validate input
        if not self._is_valid_query(query):
            logger.warning("Received empty or invalid query")
            return self.ERROR_EMPTY_QUERY
        
        cleaned_query = query.strip()
        
        try:
            # Execute reasoning
            raw_output = self._orchestrator.run(
                cleaned_query, 
                settings.max_steps
            )
            
            # Validate output
            if not raw_output or not raw_output.strip():
                logger.warning("Orchestrator returned empty output")
                return self.ERROR_NO_OUTPUT
            
            # Verify and clean
            verified = self._verifier.verify(cleaned_query, raw_output)
            
            logger.info(f"Successfully processed query: {cleaned_query[:50]}...")
            return verified
            
        except Exception as e:
            logger.exception("Agent execution failed")
            return self.ERROR_SYSTEM
    
    def _is_valid_query(self, query: Optional[str]) -> bool:
        """
        Check if query contains meaningful content.
        
        Args:
            query: Input to validate
            
        Returns:
            True if query is non-empty string with non-whitespace content
        """
        return isinstance(query, str) and query.strip() != ""