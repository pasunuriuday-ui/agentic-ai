from enum import Enum


class AgentState(str, Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    VALIDATE = "validate"
    SYNTHESIZE = "synthesize"
    FINISH = "finish"
    ERROR = "error"