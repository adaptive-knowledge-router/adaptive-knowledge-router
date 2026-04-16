"""Orchestrator FastAPI application.

Entrypoint: ``uvicorn app.main:app --host 0.0.0.0 --port 8003``
"""

import logging
import time

import httpx
from fastapi import FastAPI, HTTPException

from app.config import settings
from app.schemas.queries import QueryRequest
from app.schemas.responses import QueryResponse
from app.services.dispatcher import Dispatcher
from app.services.synthesizer import Synthesizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Orchestrator Service", version="1.0.0")

dispatcher = Dispatcher()
synthesizer = Synthesizer()


# ── endpoints ─────────────────────────────────────────────────────────


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Accept a natural-language question, route it to the best
    retrieval strategy, and return a unified result."""
    logger.info("Incoming query: %s  (top_k=%d)", req.query, req.top_k)

    start = time.perf_counter()
    try:
        prediction, retrieval = await dispatcher.dispatch(req.query, req.top_k)
    except ValueError as exc:
        # Unknown strategy from the router.
        logger.error("Dispatch error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except httpx.TimeoutException:
        logger.error("Downstream service timed out for query: %s", req.query)
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        logger.error("Could not connect to downstream service for query: %s", req.query)
        raise HTTPException(status_code=502, detail="Could not connect to downstream service")
    except httpx.HTTPStatusError as exc:
        logger.error("Downstream HTTP error %s: %s", exc.response.status_code, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Downstream service returned {exc.response.status_code}",
        )

    total_ms = (time.perf_counter() - start) * 1000.0

    response = await synthesizer.build_response(
        query=req.query,
        prediction=prediction,
        retrieval=retrieval,
        total_latency_ms=round(total_ms, 2),
    )

    logger.info(
        "Response ready: strategy=%s confidence=%.3f results=%d latency=%.1fms",
        response.strategy,
        response.confidence,
        len(response.results),
        response.latency_ms,
    )
    return response


@app.get("/health")
async def health() -> dict:
    """Liveness probe – confirms the orchestrator process is up."""
    return {"status": "ok"}


@app.get("/readiness")
async def readiness() -> dict:
    """Readiness probe – checks all downstream services."""
    import httpx

    checks: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in [
            ("router", f"{settings.router_url}/health"),
            ("kg", f"{settings.kg_url}/kg/health"),
            ("rag", f"{settings.rag_url}/health"),
        ]:
            try:
                r = await client.get(url)
                data = r.json()
                checks[name] = data.get("status", "unknown")
            except Exception as exc:
                checks[name] = f"unreachable: {type(exc).__name__}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "services": checks}
