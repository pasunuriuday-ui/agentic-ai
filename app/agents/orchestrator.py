import logging
from dataclasses import dataclass
from typing import List, Protocol, Union

from app.agents.parser import parse_action

logger = logging.getLogger(__name__)


class LLMProtocol(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class ToolProtocol(Protocol):
    def run(self, input_data: str) -> str:
        ...


@dataclass(frozen=True)
class ReasoningStep:
    action: str
    input_data: str
    observation: str


class Orchestrator:
    ERROR_INVALID_RESPONSE = "Unable to complete reasoning reliably."
    ERROR_UNKNOWN_ACTION = "Unable to complete reasoning reliably."

    def __init__(self, llm: LLMProtocol, tools: dict[str, ToolProtocol]) -> None:
        self._llm = llm
        self._tools = tools

    def run(self, query: str, max_steps: int) -> str:
        history: List[ReasoningStep] = []

        for step_number in range(max_steps):
            result = self._execute_step(query, history, step_number)

            if isinstance(result, str):
                return result

            history.append(result)

        return "Max reasoning steps reached."

    def _execute_step(
        self,
        query: str,
        history: List[ReasoningStep],
        step_number: int,
    ) -> Union[ReasoningStep, str]:

        print(f"STEP RUNNING {step_number}")  # ✅ agent loop proof

        prompt = self._build_prompt(query, history)

        # ✅ CORRECT try/except (THIS FIXES YOUR ERROR)
        try:
            response = self._llm.generate(prompt)
        except Exception as error:
            print("ERROR:", error)
            return self.ERROR_INVALID_RESPONSE

        action, tool_input, final_answer = parse_action(response)

        if final_answer is not None:
            print("FINAL ANSWER GENERATED")
            return final_answer.strip()

        if not action:
            return self.ERROR_INVALID_RESPONSE

        if action not in self._tools:
            return self.ERROR_UNKNOWN_ACTION

        print(f"CALLING TOOL: {action}")  # ✅ decision proof

        tool = self._tools[action]

        try:
            observation = tool.run(tool_input or "")
        except Exception as error:
            observation = f"Tool error: {error}"

        return ReasoningStep(
            action=action,
            input_data=tool_input or "",
            observation=observation,
        )

    def _build_prompt(self, query: str, history: List[ReasoningStep]) -> str:
        history_str = self._format_history(history)

        tool_list = "\n".join(f"- {name}" for name in self._tools.keys())

        return f"""
You are an AI agent.

Available Tools:
{tool_list}

Rules:
- Use tools if needed
- Final answer must be ONE sentence
- Return JSON ONLY

Format:
{{"final_answer": "answer"}}
or
{{"action": "tool_name", "input": "query"}}

Question:
{query}

History:
{history_str}
"""

    def _format_history(self, history: List[ReasoningStep]) -> str:
        if not history:
            return "No previous actions."

        return "\n".join(
            f"{i+1}. {step.action} -> {step.observation[:50]}"
            for i, step in enumerate(history)
        )