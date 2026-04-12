import logging
from typing import Optional

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Base exception for LLM service failures."""
    pass


class LLMConnectionError(LLMServiceError):
    """Failed to connect to or communicate with Ollama."""
    pass


class LLMResponseError(LLMServiceError):
    """Received invalid or unexpected response from Ollama."""
    pass


class LLMService:
    """
    Client for Ollama LLM API with robust error handling and connection management.
    """
    
    DEFAULT_BASE_URL: str = "http://localhost:11434"
    DEFAULT_MODEL: str = "llama3"
    DEFAULT_TIMEOUT: int = 30
    GENERATE_ENDPOINT: str = "/api/generate"
    
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
        stream: bool = False
    ) -> None:
        """
        Initialize LLM service client.
        
        Args:
            base_url: Ollama server URL (default: http://localhost:11434)
            model: Model name to use (default: llama3)
            timeout: Request timeout in seconds
            stream: Whether to stream responses (default: False for synchronous)
        """
        self._base_url = base_url.rstrip("/")
        self._url = f"{self._base_url}{self.GENERATE_ENDPOINT}"
        self._model = model
        self._timeout = timeout
        self._stream = stream
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        logger.info(f"Initialized LLM service: model={model}, url={self._base_url}")
    
    def generate(self, prompt: str) -> str:
        """
        Generate text completion from the LLM.
        
        Args:
            prompt: The input text prompt (must be non-empty)
            
        Returns:
            Generated text response (stripped of whitespace)
            
        Raises:
            ValueError: If prompt is empty or whitespace-only
            LLMConnectionError: On network/connection failures
            LLMResponseError: On invalid or missing response data
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        payload = {
            "model": self._model,
            "prompt": prompt.strip(),
            "stream": self._stream,
        }
        
        try:
            response = self._session.post(
                self._url,
                json=payload,
                timeout=self._timeout
            )
            response.raise_for_status()
            
        except Timeout:
            logger.error(f"Request to Ollama timed out after {self._timeout}s")
            raise LLMConnectionError(
                f"Request timed out after {self._timeout} seconds"
            ) from None
            
        except ConnectionError as e:
            logger.error(f"Cannot connect to Ollama at {self._base_url}: {e}")
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                "Ensure Ollama is running."
            ) from e
            
        except RequestException as e:
            logger.error(f"Request to Ollama failed: {e}")
            raise LLMConnectionError(f"Request failed: {e}") from e
        
        return self._parse_response(response)
    
    def _parse_response(self, response: requests.Response) -> str:
        """
        Extract and validate the response text from Ollama JSON.
        
        Args:
            response: Successful HTTP response object
            
        Returns:
            Cleaned response string
            
        Raises:
            LLMResponseError: If response JSON is invalid or missing expected fields
        """
        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Invalid JSON from Ollama: {e}")
            raise LLMResponseError("Invalid JSON response from Ollama") from e
        
        if not isinstance(data, dict):
            raise LLMResponseError(f"Expected dict response, got {type(data).__name__}")
        
        result = data.get("response")
        if result is None:
            logger.error(f"Missing 'response' field. Available: {list(data.keys())}")
            raise LLMResponseError(
                "Ollama response missing 'response' field. "
                f"Got keys: {list(data.keys())}"
            )
        
        if not isinstance(result, str):
            raise LLMResponseError(
                f"Expected string response, got {type(result).__name__}"
            )
        
        cleaned = result.strip()
        logger.debug(f"Generated {len(cleaned)} characters")
        
        return cleaned
    
    def health_check(self) -> bool:
        """
        Verify connectivity to Ollama server.
        
        Returns:
            True if server is reachable and model is available
        """
        try:
            # Ollama has a tags endpoint to list models
            resp = self._session.get(
                f"{self._base_url}/api/tags",
                timeout=5
            )
            resp.raise_for_status()
            return True
        except RequestException:
            return False
    
    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False