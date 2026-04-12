from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, final

from app.agents.planner import Planner
from app.agents.executor import Executor
from app.agents.validator import Validator
from app.agents.synthesizer import Synthesizer


logger = logging.getLogger(__name__)


class AgentError(Enum):
    INVALID_INPUT = auto()
    MAX_STEPS_EXCEEDED = auto()
    SAFETY_VIOLATION = auto()


@dataclass(frozen=True)
class AgentResult:
    success: bool
    answer: Optional[str] = None
    error: Optional[AgentError] = None
    steps_taken: int = 0
    latency_ms: float = 0.0
    trace: List[str] = field(default_factory=list)  # ✅ TRACE ADDED


class AgentState(Enum):
    PLAN = auto()
    EXECUTE = auto()
    VALIDATE = auto()
    SYNTHESIZE = auto()
    FINISH = auto()
    ERROR = auto()


@dataclass
class AgentContext:
    query: str
    tool_name: Optional[str] = None
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    final_answer: Optional[str] = None
    trace: List[str] = field(default_factory=list)  # ✅ TRACE ADDED


class PlannerProtocol(Protocol):
    def plan(self, query: str) -> Dict[str, Any]: ...


class ExecutorProtocol(Protocol):
    def execute(self, tool_name: str, tool_input: str): ...


class ValidatorProtocol(Protocol):
    def validate(self, output: str) -> bool: ...


class SynthesizerProtocol(Protocol):
    def synthesize(self, query: str, context: str): ...


@final
class StateMachineAgent:

    def __init__(
        self,
        llm: Any,
        tools: Dict[str, Any],
        planner: Optional[PlannerProtocol] = None,
        executor: Optional[ExecutorProtocol] = None,
        validator: Optional[ValidatorProtocol] = None,
        synthesizer: Optional[SynthesizerProtocol] = None,
    ):
        self._tools = tools
        self._planner = planner or Planner()
        self._executor = executor or Executor(tools)
        self._validator = validator or Validator()
        self._synthesizer = synthesizer or Synthesizer(llm)

    def run(self, query: str) -> AgentResult:

        if not query or not query.strip():
            return AgentResult(success=False, error=AgentError.INVALID_INPUT)

        context = AgentContext(query=query.strip())
        state = AgentState.PLAN

        steps = 0
        start = time.perf_counter()

        while state not in [AgentState.FINISH, AgentState.ERROR]:

            steps += 1
            if steps > 5:
                return AgentResult(success=False, error=AgentError.MAX_STEPS_EXCEEDED)

            if state == AgentState.PLAN:
                plan = self._planner.plan(context.query)
                context.tool_name = plan.get("tool")
                context.tool_input = plan.get("input")

                # ✅ TRACE
                context.trace.append(
                    f"PLAN → tool={context.tool_name}, input={context.tool_input}"
                )

                state = AgentState.EXECUTE

            elif state == AgentState.EXECUTE:
                result = self._executor.execute(
                    context.tool_name,
                    context.tool_input or ""
                )
                context.tool_output = result.output

                # ✅ TRACE
                context.trace.append(
                    f"EXECUTE → output={str(context.tool_output)[:100]}"
                )

                state = AgentState.VALIDATE

            elif state == AgentState.VALIDATE:
                is_valid = self._validator.validate(context.tool_output)

                # ✅ TRACE
                context.trace.append(f"VALIDATE → passed={is_valid}")

                if not context.tool_output or not is_valid:
                    state = AgentState.ERROR
                else:
                    state = AgentState.SYNTHESIZE

            elif state == AgentState.SYNTHESIZE:
                result = self._synthesizer.synthesize(
                    context.query,
                    context.tool_output
                )

                if not result.success:
                    state = AgentState.ERROR
                else:
                    context.final_answer = result.answer

                    # ✅ TRACE
                    context.trace.append(
                        f"SYNTHESIZE → answer={context.final_answer}"
                    )

                    state = AgentState.FINISH

        latency = (time.perf_counter() - start) * 1000

        if state == AgentState.FINISH:
            return AgentResult(
                success=True,
                answer=context.final_answer,
                steps_taken=steps,
                latency_ms=latency,
                trace=context.trace  # ✅ RETURN TRACE
            )

        return AgentResult(
            success=False,
            error=AgentError.SAFETY_VIOLATION,
            steps_taken=steps,
            latency_ms=latency,
            trace=context.trace  # ✅ RETURN TRACE
        )