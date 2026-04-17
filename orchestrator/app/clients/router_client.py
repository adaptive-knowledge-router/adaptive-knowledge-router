"""HTTP client for the router service."""

import logging

import httpx

from app.config import settings
from app.schemas.responses import StrategyResponse

logger = logging.getLogger(__name__)

# Router service endpoint path (matches router-service app.py).
PREDICT_PATH = "/router/predict"

# HTTP status codes treated as transient (worth retrying).
_RETRYABLE_STATUS = {502, 503, 504}


class RouterClient:
    """Async client that calls the router service for strategy prediction."""

    def __init__(self) -> None:
        self._base_url = settings.router_url
        self._timeout = settings.request_timeout
        self._max_retries = settings.max_retries

    async def predict(self, query: str) -> StrategyResponse:
        """Send a query to the router and return the predicted strategy.

        Retries on transient network/server errors up to ``max_retries`` times.

        Raises:
            httpx.HTTPStatusError: on non-retryable 4xx/5xx after exhausting retries.
            httpx.ConnectError | httpx.TimeoutException: if the service is unreachable.
        """
        url = f"{self._base_url}{PREDICT_PATH}"
        last_exc: Exception | None = None

        for attempt in range(1 + self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json={"query": query})

                if resp.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                    logger.warning(
                        "Router returned %s (attempt %d/%d), retrying",
                        resp.status_code,
                        attempt + 1,
                        1 + self._max_retries,
                    )
                    continue

                resp.raise_for_status()
                data = resp.json()
                return StrategyResponse(**data)

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    logger.warning(
                        "Router request failed (%s, attempt %d/%d), retrying",
                        type(exc).__name__,
                        attempt + 1,
                        1 + self._max_retries,
                    )
                    continue
                raise

        # Should not be reached, but satisfies the type checker.
        raise last_exc  # type: ignore[misc]
