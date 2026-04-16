"""HTTP client for the KG service."""

import logging
import time

import httpx

from app.config import settings
from app.schemas.responses import RetrievalResult

logger = logging.getLogger(__name__)

# KG service natural-language endpoint paths (GET, ?question=…).
ENTITY_PATH = "/kg/query/entity"
RELATION_PATH = "/kg/query/relation"
MULTI_HOP_PATH = "/kg/query/multi_hop"

# Strategy name ↔ endpoint mapping.
_STRATEGY_PATHS: dict[str, str] = {
    "entity_lookup": ENTITY_PATH,
    "relation_filter": RELATION_PATH,
    "multi_hop": MULTI_HOP_PATH,
}

# HTTP status codes treated as transient (worth retrying).
_RETRYABLE_STATUS = {502, 503, 504}


class KGClient:
    """Async client that calls the KG service for structured queries."""

    def __init__(self) -> None:
        self._base_url = settings.kg_url
        self._timeout = settings.request_timeout
        self._max_retries = settings.max_retries

    # ── public methods ────────────────────────────────────────────────

    async def entity_lookup(self, question: str) -> RetrievalResult:
        """Call the entity_lookup NL endpoint."""
        return await self._call("entity_lookup", question)

    async def relation_filter(self, question: str) -> RetrievalResult:
        """Call the relation_filter NL endpoint."""
        return await self._call("relation_filter", question)

    async def multi_hop(self, question: str) -> RetrievalResult:
        """Call the multi_hop NL endpoint."""
        return await self._call("multi_hop", question)

    # ── internals ─────────────────────────────────────────────────────

    async def _call(self, strategy: str, question: str) -> RetrievalResult:
        """Send *question* to the matching KG endpoint and return a
        normalised ``RetrievalResult``.

        Retries on transient network / server errors up to
        ``settings.max_retries`` times.
        """
        path = _STRATEGY_PATHS[strategy]
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None

        for attempt in range(1 + self._max_retries):
            try:
                start = time.perf_counter()
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(url, params={"question": question})
                elapsed_ms = (time.perf_counter() - start) * 1000.0

                if resp.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                    logger.warning(
                        "KG %s returned %s (attempt %d/%d), retrying",
                        strategy,
                        resp.status_code,
                        attempt + 1,
                        1 + self._max_retries,
                    )
                    continue

                resp.raise_for_status()
                data = resp.json()

                return RetrievalResult(
                    strategy=strategy,
                    results=data.get("results", []),
                    latency_ms=elapsed_ms,
                    source="kg",
                )

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    logger.warning(
                        "KG %s request failed (%s, attempt %d/%d), retrying",
                        strategy,
                        type(exc).__name__,
                        attempt + 1,
                        1 + self._max_retries,
                    )
                    continue
                raise

        raise last_exc  # type: ignore[misc]
