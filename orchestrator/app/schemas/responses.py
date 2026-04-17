"""Response schemas for the orchestrator API."""

from typing import Optional

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


class SynthesisMetadata(BaseModel):
    """Metadata about the LLM synthesis step."""

    model: str = Field(description="Ollama model used (or attempted) for synthesis.")
    query_mode: str = Field(
        default="fallback",
        description="Query mode used: exact_lookup, list_query, open_explanation, compare_query, fallback.",
    )
    retrieval_latency_ms: float = Field(
        default=0.0,
        description="Downstream retrieval latency in milliseconds.",
    )
    synthesis_latency_ms: float = Field(
        default=0.0,
        description="LLM generation latency in milliseconds (0 for direct extraction).",
    )
    total_latency_ms: float = Field(
        default=0.0,
        description="retrieval_latency_ms + synthesis_latency_ms.",
    )
    used_results_count: int = Field(
        default=0,
        description="Number of retrieved results fed to the LLM.",
    )
    cached: bool = Field(
        default=False,
        description="True if this answer was served from the in-memory cache.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if synthesis failed; null on success.",
    )


class QueryResponse(BaseModel):
    """Top-level response for POST /query."""

    query: str = Field(description="Original user query.")
    strategy: str = Field(description="Strategy selected by the router.")
    confidence: float = Field(description="Router confidence for the selected strategy.")
    synthesized_answer: Optional[str] = Field(
        default=None,
        description="Concise answer synthesised by the LLM from the retrieved results.",
    )
    synthesis_metadata: Optional[SynthesisMetadata] = Field(
        default=None,
        description="Metadata about the synthesis step (model, latency, errors).",
    )
    results: list[dict] = Field(default_factory=list, description="Retrieved result records.")
    latency_ms: float = Field(description="Total orchestration latency in milliseconds.")
    source: str = Field(description="Service that produced results: 'kg' or 'rag'.")
