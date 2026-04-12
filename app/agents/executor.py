from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any, 
    Callable, 
    Dict, 
    Optional, 
    Protocol, 
    TypeVar, 
    Generic,
    runtime_checkable,
    Union
)
from functools import wraps
import logging
import time
import asyncio
import re  # ✅ FIX: REQUIRED FOR regex

from contextlib import contextmanager
from concurrent.futures import TimeoutError as FutureTimeoutError, ThreadPoolExecutor
import traceback


# Module-level logging
logger = logging.getLogger(__name__)


class ExecutionError(Enum):
    """Taxonomy of execution failure modes for precise handling."""
    TOOL_NOT_FOUND = auto()
    INVALID_INPUT = auto()
    EXECUTION_TIMEOUT = auto()
    EXECUTION_EXCEPTION = auto()
    CIRCUIT_OPEN = auto()
    RATE_LIMITED = auto()
    PERMISSION_DENIED = auto()


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    output: Optional[str] = None
    error: Optional[ExecutionError] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def failed(self) -> bool:
        return not self.success
    
    def unwrap(self) -> str:
        if not self.success or self.output is None:
            raise ExecutionFailureError(self.error, self.metadata)
        return self.output


class ExecutionFailureError(Exception):
    def __init__(self, error: Optional[ExecutionError], metadata: Dict[str, Any]):
        self.error = error
        self.metadata = metadata
        super().__init__(f"Execution failed: {error}")


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    version: str = "1.0.0"
    
    def run(self, input_data: str) -> str:
        ...
    
    def validate(self, input_data: str) -> bool:
        return True


@dataclass(frozen=True)
class ExecutionConfig:
    default_timeout: float = 30.0
    max_retries: int = 0
    enable_circuit_breaker: bool = True
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    max_input_length: int = 10000
    sanitize_output: bool = True
    forbidden_output_patterns: list[str] = field(default_factory=lambda: [
        r"password\s*[=:]\s*\S+",
        r"token\s*[=:]\s*\S+",
        r"api[_-]?key\s*[=:]\s*\S+",
    ])


class CircuitBreaker:
    def __init__(self, failure_threshold: int, recovery_timeout: float):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"
        self._lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None
    
    def can_execute(self) -> bool:
        now = time.time()
        
        if self.state == "CLOSED":
            return True
            
        if self.state == "OPEN":
            if self.last_failure_time and (now - self.last_failure_time) >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker entering HALF_OPEN state")
                return True
            return False
            
        return True
    
    def record_success(self) -> None:
        self.failures = 0
        self.state = "CLOSED"
    
    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPENED after {self.failures} failures")


class Executor:
    def __init__(
        self,
        tools: Dict[str, Tool],
        config: Optional[ExecutionConfig] = None,
        middleware: Optional[list[Callable[[str, str, Callable], Any]]] = None
    ):
        self._tools = dict(tools)
        self._config = config or ExecutionConfig()
        self._middleware = middleware or []
        self._circuit_breakers: Dict[str, CircuitBreaker] = {
            name: CircuitBreaker(
                self._config.failure_threshold,
                self._config.recovery_timeout
            )
            for name in tools
        }
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._compiled_patterns = [
            re.compile(pattern, re.I)  # ✅ NOW WORKS
            for pattern in self._config.forbidden_output_patterns
        ]
    
    def _sanitize_input(self, tool_input: str) -> str:
        if not isinstance(tool_input, str):
            raise TypeError(f"Expected str, got {type(tool_input)}")
        cleaned = tool_input.replace('\x00', '')
        return cleaned[:self._config.max_input_length]
    
    def _sanitize_output(self, output: str) -> str:
        if not self._config.sanitize_output:
            return output
        
        redacted = output
        for pattern in self._compiled_patterns:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    
    def _validate_tool_access(self, tool_name: str) -> Optional[ExecutionResult]:
        if not tool_name:
            return ExecutionResult(success=False, error=ExecutionError.TOOL_NOT_FOUND)
        
        if tool_name not in self._tools:
            return ExecutionResult(success=False, error=ExecutionError.TOOL_NOT_FOUND)
        
        breaker = self._circuit_breakers[tool_name]
        if not breaker.can_execute():
            return ExecutionResult(success=False, error=ExecutionError.CIRCUIT_OPEN)
        
        return None
    
    def _execute_with_timeout(self, tool: Tool, tool_input: str, timeout: float) -> str:
        future = self._executor.submit(tool.run, tool_input)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            future.cancel()
            raise TimeoutError("Timeout")
    
    def execute(self, tool_name: str, tool_input: Optional[str] = None) -> ExecutionResult:
        start = time.perf_counter()
        
        validation = self._validate_tool_access(tool_name)
        if validation:
            return validation
        
        tool = self._tools[tool_name]
        breaker = self._circuit_breakers[tool_name]
        
        try:
            safe_input = self._sanitize_input(tool_input or "")
            output = self._execute_with_timeout(tool, safe_input, self._config.default_timeout)
            safe_output = self._sanitize_output(output)
            breaker.record_success()
            
            return ExecutionResult(
                success=True,
                output=safe_output,
                duration_ms=(time.perf_counter() - start) * 1000
            )
            
        except Exception:
            breaker.record_failure()
            return ExecutionResult(
                success=False,
                error=ExecutionError.EXECUTION_EXCEPTION,
                duration_ms=(time.perf_counter() - start) * 1000
            )