"""
Application configuration module.

Centralizes all environment-specific settings using Pydantic Settings
for automatic validation, type safety, and environment variable loading.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Environment variables override default values automatically.
    All settings are validated on instantiation.
    """
    
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )
    
    # Processing configuration
    max_steps: int = Field(
        default=4,
        ge=1,
        le=100,
        description="Maximum number of processing steps per request",
    )
    
    # Vector store configuration
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        min_length=1,
        description="HuggingFace embedding model identifier",
    )
    collection_name: str = Field(
        default="documents",
        min_length=1,
        max_length=128,
        description="Vector database collection name",
    )
    
    @field_validator("collection_name")
    @classmethod
    def _validate_collection_name(cls, value: str) -> str:
        """Ensure collection name uses only lowercase alphanumeric and underscores."""
        normalized = value.lower().strip()
        if not normalized.replace("_", "").isalnum():
            raise ValueError(
                "Collection name must contain only letters, numbers, and underscores"
            )
        return normalized


@lru_cache
def get_settings() -> Settings:
    """
    Return cached Settings instance.
    
    Uses singleton pattern to avoid re-reading environment on every call.
    """
    return Settings()


# Global settings instance for convenient imports
settings = get_settings()