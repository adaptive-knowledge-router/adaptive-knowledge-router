"""HTTP client for the RAG service."""

import logging
import time

import httpx

from app.config import settings
from app.schemas.responses import RetrievalResult

logger = logging.getLogger(__name__)

# RAG service endpoint paths (GET, ?query=…&top_k=…).
SPARSE_PATH = "/rag/sparse"
DENSE_PATH = "/rag/dense"
HYBRID_PATH = "/rag/hybrid"

# Strategy name ↔ endpoint mapping.
_STRATEGY_PATHS: dict[str, str] = {
    "sparse": SPARSE_PATH,
    "dense": DENSE_PATH,
    "hybrid": HYBRID_PATH,
}

# HTTP status codes treated as transient (worth retrying).
_RETRYABLE_STATUS = {502, 503, 504}


class RAGClient:
    """Async client that calls the RAG service for retrieval."""

    def __init__(self) -> None:
        self._base_url = settings.rag_url
        self._timeout = settings.request_timeout
        self._max_retries = settings.max_retries

    # ── public methods ────────────────────────────────────────────────

    async def sparse(self, query: str, top_k: int) -> RetrievalResult:
        """Call the BM25 sparse retrieval endpoint."""
        return await self._call("sparse", query, top_k)

    async def dense(self, query: str, top_k: int) -> RetrievalResult:
        """Call the FAISS dense retrieval endpoint."""
        return await self._call("dense", query, top_k)

    async def hybrid(self, query: str, top_k: int) -> RetrievalResult:
        """Call the hybrid (BM25 + dense + reranker) endpoint."""
        return await self._call("hybrid", query, top_k)

    # ── internals ─────────────────────────────────────────────────────

    async def _call(self, strategy: str, query: str, top_k: int) -> RetrievalResult:
        """Send *query* to the matching RAG endpoint and return a
        normalised ``RetrievalResult``.

        Uses ``latency_ms`` from the upstream response when available;
        otherwise measures round-trip time client-side.
        """
        path = _STRATEGY_PATHS[strategy]
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None

        for attempt in range(1 + self._max_retries):
            try:
                start = time.perf_counter()
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(
                        url, params={"query": query, "top_k": top_k}
                    )
                elapsed_ms = (time.perf_counter() - start) * 1000.0

                if resp.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                    logger.warning(
                        "RAG %s returned %s (attempt %d/%d), retrying",
                        strategy,
                        resp.status_code,
                        attempt + 1,
                        1 + self._max_retries,
                    )
                    continue

                resp.raise_for_status()
                data = resp.json()

                # RAG service returns errors as HTTP 200 with an "error" key.
                if "error" in data:
                    raise httpx.HTTPStatusError(
                        f"RAG {strategy} error: {data['error']}",
                        request=resp.request,
                        response=resp,
                    )

                # Prefer server-reported latency; fall back to client-side.
                latency = data.get("latency_ms")
                if latency is None:
                    latency = elapsed_ms

                return RetrievalResult(
                    strategy=strategy,
                    results=data.get("results", []),
                    latency_ms=latency,
                    source="rag",
                )

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    logger.warning(
                        "RAG %s request failed (%s, attempt %d/%d), retrying",
                        strategy,
                        type(exc).__name__,
                        attempt + 1,
                        1 + self._max_retries,
                    )
                    continue
                raise

        raise last_exc  # type: ignore[misc]
