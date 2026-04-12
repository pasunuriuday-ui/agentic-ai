import json
from typing import Optional, Tuple


def parse_action(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse a JSON text to extract action, input, or final answer.
    
    Args:
        text: JSON string to parse
        
    Returns:
        Tuple of (action, input, final_answer) where:
        - action: The action type, or None if final_answer present or invalid
        - input: The action input value, or None
        - final_answer: The final answer string, or None if action present
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, None, None
    
    # Final answer takes precedence over actions
    if "final_answer" in data:
        return None, None, data["final_answer"]
    
    action = data.get("action")
    action_input = data.get("input")
    
    return action, action_input, None