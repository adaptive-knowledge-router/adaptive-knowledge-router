"""Request schemas for the orchestrator API."""

from pydantic import BaseModel, Field, field_validator

from app.config import settings


class QueryRequest(BaseModel):
    """Top-level request body for POST /query."""

    query: str = Field(
        ...,
        description="Natural-language question to route and answer.",
    )
    top_k: int = Field(
        default=settings.default_top_k,
        gt=0,
        le=20,
        description="Number of results to return from retrieval (1-20).",
    )
    include_metadata: bool = Field(
        default=True,
        description="Include routing metadata (strategy, confidence, latency) in the response.",
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty or whitespace")
        return v
