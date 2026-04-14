"""Dispatcher – routes a query through the router and into the correct
retrieval backend (KG or RAG)."""

import logging
import re
from collections.abc import Awaitable, Callable

from app.clients.kg_client import KGClient
from app.clients.rag_client import RAGClient
from app.clients.router_client import RouterClient
from app.schemas.responses import RetrievalResult, StrategyResponse

logger = logging.getLogger(__name__)

# Strategies served by each backend.
KG_STRATEGIES = {"entity_lookup", "relation_filter", "multi_hop"}
RAG_STRATEGIES = {"sparse", "dense", "hybrid"}
ALL_STRATEGIES = KG_STRATEGIES | RAG_STRATEGIES

# Deterministic patterns that always belong in KG entity_lookup,
# regardless of what the router model predicts.
_PAPER_ID_RE = re.compile(r"\b\d{4}\.\d{4,5}\b")
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")


class Dispatcher:
    """Accepts a user query, classifies it via the router, then calls
    the appropriate KG or RAG client method and returns a unified
    ``RetrievalResult``.
    """

    def __init__(self) -> None:
        self._router = RouterClient()
        self._kg = KGClient()
        self._rag = RAGClient()

        # Strategy name → callable that returns a RetrievalResult.
        # KG methods take (question); RAG methods take (query, top_k).
        # We normalise them in dispatch() so the map stays simple.
        self._kg_methods: dict[str, Callable[[str], Awaitable[RetrievalResult]]] = {
            "entity_lookup": self._kg.entity_lookup,
            "relation_filter": self._kg.relation_filter,
            "multi_hop": self._kg.multi_hop,
        }
        self._rag_methods: dict[str, Callable[[str, int], Awaitable[RetrievalResult]]] = {
            "sparse": self._rag.sparse,
            "dense": self._rag.dense,
            "hybrid": self._rag.hybrid,
        }

    async def dispatch(self, query: str, top_k: int) -> tuple[StrategyResponse, RetrievalResult]:
        """Route *query* and execute the predicted retrieval strategy.

        Returns:
            A tuple of (router_prediction, retrieval_result).

        Raises:
            ValueError: if the router returns an unknown strategy.
        """
        # 0. Deterministic override — paper IDs and DOIs always go to KG
        override = None
        if _PAPER_ID_RE.search(query) or _DOI_RE.search(query):
            override = "entity_lookup"
            logger.info("Deterministic override: query contains paper ID or DOI → entity_lookup")

        # 1. Classify (always call router for probabilities / logging)
        prediction = await self._router.predict(query)
        strategy = override or prediction.strategy
        if override and override != prediction.strategy:
            logger.info(
                "Router predicted %s (%.3f) but overridden to %s",
                prediction.strategy,
                prediction.confidence,
                override,
            )
            prediction = StrategyResponse(
                strategy=override,
                confidence=prediction.confidence,
                probabilities=prediction.probabilities,
            )
        else:
            logger.info(
                "Router selected strategy=%s confidence=%.3f",
                strategy,
                prediction.confidence,
            )

        # 2. Dispatch to the right backend
        if strategy in self._kg_methods:
            result = await self._kg_methods[strategy](query)
        elif strategy in self._rag_methods:
            result = await self._rag_methods[strategy](query, top_k)
        else:
            raise ValueError(
                f"Unknown strategy '{strategy}' returned by router. "
                f"Expected one of {sorted(ALL_STRATEGIES)}."
            )

        logger.info(
            "Retrieval complete: strategy=%s source=%s results=%d latency=%.1fms",
            result.strategy,
            result.source,
            len(result.results),
            result.latency_ms,
        )

        return prediction, result
