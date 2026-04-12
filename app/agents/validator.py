from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Set, Optional, Callable
import re


class ValidationError(Enum):
    EMPTY_OUTPUT = auto()
    TOO_SHORT = auto()
    BLOCKED_PATTERN = auto()


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    error: Optional[ValidationError] = None
    message: str = ""
    blocked_term: Optional[str] = None

    @property
    def failed(self) -> bool:
        return not self.is_valid


class ValidationConfig:
    
    # ✅ FIX: REDUCED LENGTH (ONLY CHANGE)
    DEFAULT_MIN_LENGTH: int = 5

    DEFAULT_BLOCKED_PATTERNS: Set[str] = frozenset({
        "no relevant",
        "no documents", 
        "not found",
        "failed",
        "error",
        "unavailable",
        "empty",
        "null",
        "none"
    })

    def __init__(
        self,
        min_length: Optional[int] = None,
        blocked_patterns: Optional[Set[str]] = None,
        case_sensitive: bool = False,
        custom_validators: Optional[List[Callable[[str], bool]]] = None
    ):
        self.min_length = min_length or self.DEFAULT_MIN_LENGTH
        self.blocked_patterns = blocked_patterns or set(self.DEFAULT_BLOCKED_PATTERNS)
        self.case_sensitive = case_sensitive
        self.custom_validators = custom_validators or []


class Validator:
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self._config = config or ValidationConfig()
        self._compiled_patterns: List[re.Pattern] = self._compile_patterns()

    def _compile_patterns(self) -> List[re.Pattern]:
        flags = 0 if self._config.case_sensitive else re.IGNORECASE
        return [
            re.compile(re.escape(pattern), flags) 
            for pattern in self._config.blocked_patterns
        ]

    def _normalize_text(self, text: str) -> str:
        normalized = text.strip()
        if not self._config.case_sensitive:
            normalized = normalized.lower()
        return ' '.join(normalized.split())

    def validate(self, output: Optional[str]) -> ValidationResult:

        if not output:
            return ValidationResult(
                is_valid=False,
                error=ValidationError.EMPTY_OUTPUT,
                message="Output is None or empty"
            )

        text = self._normalize_text(output)

        # ✅ FIX APPLIED HERE (uses new min_length=5)
        if len(text) < self._config.min_length:
            return ValidationResult(
                is_valid=False,
                error=ValidationError.TOO_SHORT,
                message=f"Output length ({len(text)}) below minimum ({self._config.min_length})"
            )

        for pattern in self._compiled_patterns:
            match = pattern.search(text)
            if match:
                return ValidationResult(
                    is_valid=False,
                    error=ValidationError.BLOCKED_PATTERN,
                    message=f"Blocked pattern detected: '{match.group()}'",
                    blocked_term=match.group()
                )

        for validator in self._config.custom_validators:
            if not validator(text):
                return ValidationResult(
                    is_valid=False,
                    error=None,
                    message="Failed custom validation check"
                )

        return ValidationResult(
            is_valid=True,
            message="Validation passed"
        )

    def is_valid(self, output: Optional[str]) -> bool:
        return self.validate(output).is_valid

    def batch_validate(self, outputs: List[str]) -> List[ValidationResult]:
        return [self.validate(out) for out in outputs]