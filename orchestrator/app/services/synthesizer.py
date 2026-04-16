"""Synthesizer – transforms router prediction + retrieval output into
the final ``QueryResponse`` returned by the orchestrator API."""

from app.schemas.responses import QueryResponse, RetrievalResult, StrategyResponse


class Synthesizer:
    """Builds a unified ``QueryResponse`` from dispatcher outputs.

    Currently a lightweight, deterministic pass-through that preserves
    all metadata.  An optional LLM summarisation step can be enabled
    later by implementing ``_llm_summarise``.
    """

    async def build_response(
        self,
        query: str,
        prediction: StrategyResponse,
        retrieval: RetrievalResult,
        total_latency_ms: float,
    ) -> QueryResponse:
        """Assemble the final API response.

        Args:
            query: Original user question.
            prediction: Router classification result.
            retrieval: Normalised results from KG or RAG.
            total_latency_ms: Wall-clock time for the full orchestration
                pipeline (router + retrieval), measured by the caller.

        Returns:
            A ``QueryResponse`` ready to serialise to the client.
        """
        return QueryResponse(
            query=query,
            strategy=prediction.strategy,
            confidence=prediction.confidence,
            results=retrieval.results,
            latency_ms=total_latency_ms,
            source=retrieval.source,
        )
