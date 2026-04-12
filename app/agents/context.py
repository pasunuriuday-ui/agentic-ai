from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentContext:
    query: str
    tool_name: Optional[str] = None
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    final_answer: Optional[str] = None