"""Response schemas for the orchestrator API."""

from pydantic import BaseModel, Field


class StrategyResponse(BaseModel):
    """Router prediction returned by the router service."""

    strategy: str = Field(description="Predicted strategy class.")
    confidence: float = Field(description="Confidence score for the top class.")
    probabilities: dict[str, float] = Field(
        default_factory=dict,
        description="Per-class probability distribution from the router.",
    )


class RetrievalResult(BaseModel):
    """Normalised result from either KG or RAG service."""

    strategy: str = Field(description="Strategy that produced these results.")
    results: list[dict] = Field(default_factory=list, description="List of result records.")
    latency_ms: float = Field(description="Round-trip latency in milliseconds.")
    source: str = Field(description="Upstream service: 'kg' or 'rag'.")


class QueryResponse(BaseModel):
    """Top-level response for POST /query."""

    query: str = Field(description="Original user query.")
    strategy: str = Field(description="Strategy selected by the router.")
    confidence: float = Field(description="Router confidence for the selected strategy.")
    results: list[dict] = Field(default_factory=list, description="Retrieved result records.")
    latency_ms: float = Field(description="Total orchestration latency in milliseconds.")
    source: str = Field(description="Service that produced results: 'kg' or 'rag'.")
