"""
Orchestrator configuration.

All settings are read from environment variables with sensible defaults.
Defaults assume Docker Compose networking (service names as hostnames).
For local development, override with localhost URLs.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Orchestrator server ───────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8003

    # ── Downstream service URLs ───────────────────────────────────────
    # Defaults match the docker-compose service names and ports.
    router_url: str = "http://router-service:8001"
    kg_url: str = "http://kg-service:8000"
    rag_url: str = "http://rag-service:8002"

    # ── Ollama LLM (answer synthesis) ──────────────────────────────────
    ollama_url: str = "http://ollama:11434"
    answer_model: str = "qwen2.5:1.5b"
    ollama_timeout: float = 240.0

    # ── HTTP client settings ──────────────────────────────────────────
    # Timeout (seconds) for each outbound request to a downstream service.
    request_timeout: float = 120.0
    # Number of retries on transient failures (connect errors, 502/503/504).
    max_retries: int = 2

    # ── Router confidence threshold ───────────────────────────────────
    # If the router's top-class confidence is below this value the
    # orchestrator should treat the prediction as uncertain. Downstream
    # handlers can decide whether to fall back to a default strategy.
    confidence_threshold: float = 0.4

    # ── Answer cache ──────────────────────────────────────────────────
    cache_size: int = 128

    # ── Default retrieval parameters ──────────────────────────────────
    # Default number of results to request from RAG endpoints.
    default_top_k: int = 5

    model_config = {
        "env_prefix": "ORCH_",          # e.g. ORCH_ROUTER_URL overrides router_url
        "env_file": ".env",             # optional .env file support
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Single instance imported by the rest of the application.
settings = Settings()
