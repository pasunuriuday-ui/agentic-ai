from typing import Optional

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    """
    Request model for query submission.
    
    Validates that queries are within acceptable length bounds
    and contain meaningful content (not just whitespace).
    """
    
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="The user's question or task for the agent to process.",
        examples=["What is the capital of France?"]
    )
    
    @field_validator("query")
    @classmethod
    def validate_not_whitespace(cls, value: str) -> str:
        """
        Ensure query contains non-whitespace characters.
        
        Pydantic's min_length counts all characters, so we explicitly
        check for meaningful content to reject strings like "   ".
        """
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("Query must contain at least 3 non-whitespace characters")
        return stripped


class QueryResponse(BaseModel):
    """
    Response model for query results.
    
    Follows a discriminated union pattern where success determines
    which fields are populated:
    - success=True: answer contains the result, error is None
    - success=False: error contains the message, answer is None
    """
    
    success: bool = Field(
        ...,
        description="Indicates whether the query was processed successfully."
    )
    answer: Optional[str] = Field(
        default=None,
        description="The processed answer when success is True.",
        examples=["The capital of France is Paris."]
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message when success is False.",
        examples=["Query cannot be empty."]
    )
    
    @field_validator("error")
    @classmethod
    def validate_error_on_failure(cls, error: Optional[str], info) -> Optional[str]:
        """Ensure error message is present when success is False."""
        success = info.data.get("success")
        if not success and not error:
            raise ValueError("Error message required when success is False")
        return error
    
    @field_validator("answer")
    @classmethod
    def validate_answer_on_success(cls, answer: Optional[str], info) -> Optional[str]:
        """Ensure answer is present when success is True."""
        success = info.data.get("success")
        if success and not answer:
            raise ValueError("Answer required when success is True")
        return answer
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "answer": "The capital of France is Paris.",
                    "error": None
                },
                {
                    "success": False,
                    "answer": None,
                    "error": "Unable to generate reliable answer."
                }
            ]
        }
    }