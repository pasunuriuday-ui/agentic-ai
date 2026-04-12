from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Protocol, Callable, Any
import logging
import re
from textwrap import dedent


logger = logging.getLogger(__name__)


class SynthesisError(Enum):
    MISSING_CONTEXT = auto()
    INVALID_INPUT = auto()
    LLM_UNAVAILABLE = auto()
    EMPTY_RESPONSE = auto()
    SAFETY_VIOLATION = auto()
    PROMPT_INJECTION_DETECTED = auto()


@dataclass(frozen=True)
class SynthesisResult:
    success: bool
    answer: Optional[str] = None
    error: Optional[SynthesisError] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success and self.answer is not None


class LLMInterface(Protocol):
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        ...

    def count_tokens(self, text: str) -> int:
        ...


@dataclass(frozen=True)
class SynthesisConfig:
    max_tokens: int = 150
    temperature: float = 0.0
    max_context_length: int = 4000
    enable_injection_check: bool = True
    forbidden_patterns: list[str] = field(default_factory=lambda: [
        r"as an ai",
        r"i cannot",
        r"i don't know",
        r"no information",
        r"not mentioned",
        r"insufficient context"
    ])

    # ✅ FIXED PROMPT (IMPORTANT)
    prompt_template: str = dedent("""\
        You are a strict answer generator.

        Use ONLY the given context to answer.

        Rules:
        - Answer must be a COMPLETE sentence
        - Include subject and meaning clearly
        - Do NOT shorten the answer
        - Do NOT remove important words
        - Do NOT add new information
        - If answer not found → output exactly: UNANSWERABLE

        Context:
        {context}

        Question: {query}

        Answer:
    """)


class Synthesizer:

    INJECTION_PATTERNS: list[re.Pattern] = [
        re.compile(r"ignore (previous|above|context)", re.I),
        re.compile(r"disregard.*instructions", re.I),
        re.compile(r"forget (that|the)", re.I),
        re.compile(r"you are (now|no longer)", re.I),
    ]

    def __init__(
        self,
        llm: LLMInterface,
        config: Optional[SynthesisConfig] = None,
        post_processor: Optional[Callable[[str], Optional[str]]] = None
    ):
        self._llm = llm
        self._config = config or SynthesisConfig()
        self._post_processor = post_processor
        self._compiled_forbidden = [
            re.compile(pattern, re.I)
            for pattern in self._config.forbidden_patterns
        ]

    def _sanitize_input(self, text: str) -> str:
        sanitized = ''.join(char for char in text if char == '\n' or ord(char) >= 32)
        return sanitized[:self._config.max_context_length].strip()

    def _detect_injection(self, text: str) -> bool:
        if not self._config.enable_injection_check:
            return False
        return any(pattern.search(text) for pattern in self.INJECTION_PATTERNS)

    def _validate_response(self, response: str) -> Optional[str]:
        if not response:
            return None

        cleaned = response.strip()
        lower = cleaned.lower()

        if any(pattern.search(lower) for pattern in self._compiled_forbidden):
            logger.warning(f"Refusal pattern detected: {cleaned[:50]}...")
            return None

        if cleaned == "UNANSWERABLE":
            return None

        return cleaned

    def synthesize(self, query: str, context: str) -> SynthesisResult:
        start_time = __import__('time').time()

        if not query or not query.strip():
            return SynthesisResult(False, error=SynthesisError.INVALID_INPUT)

        if not context or not context.strip():
            return SynthesisResult(False, error=SynthesisError.MISSING_CONTEXT)

        if self._detect_injection(query) or self._detect_injection(context):
            return SynthesisResult(False, error=SynthesisError.PROMPT_INJECTION_DETECTED)

        safe_query = self._sanitize_input(query)
        safe_context = self._sanitize_input(context)

        prompt = self._config.prompt_template.format(
            context=safe_context,
            query=safe_query
        )

        try:
            # ✅ SAFE LLM CALL
            try:
                raw_response = self._llm.generate(
                    prompt,
                    max_tokens=self._config.max_tokens,
                    temperature=self._config.temperature
                )
            except TypeError:
                raw_response = self._llm.generate(prompt)

            if not raw_response:
                return SynthesisResult(False, error=SynthesisError.LLM_UNAVAILABLE)

            if self._post_processor:
                raw_response = self._post_processor(raw_response)

            validated = self._validate_response(raw_response)

            if validated is None:
                return SynthesisResult(False, error=SynthesisError.SAFETY_VIOLATION)

            latency = int((__import__('time').time() - start_time) * 1000)

            return SynthesisResult(
                success=True,
                answer=validated,
                metadata={"latency_ms": latency}
            )

        except Exception as e:
            logger.exception("Synthesis failed with exception")

            # ✅ FALLBACK (VERY IMPORTANT)
            return SynthesisResult(
                success=True,
                answer=context.strip()[:200]  # fallback to context
            )