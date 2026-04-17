"""HTTP client for the Ollama LLM service (answer synthesis)."""

import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Calls the Ollama ``/api/generate`` endpoint to synthesise a final
    answer from retrieved evidence."""

    def __init__(self) -> None:
        self._base_url = settings.ollama_url
        self._model = settings.answer_model
        self._timeout = settings.ollama_timeout

    async def generate(
        self, prompt: str, *, num_predict: int = 256,
    ) -> tuple[str, float]:
        """Send *prompt* to Ollama and return ``(response_text, latency_ms)``.

        Args:
            prompt: The text prompt.
            num_predict: Max tokens for the response.

        Raises:
            httpx.HTTPStatusError: on non-2xx responses.
            httpx.TimeoutException: if the request exceeds the timeout.
        """
        url = f"{self._base_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": num_predict,
            },
        }

        logger.info(
            "LLM request: model=%s prompt_chars=%d num_predict=%d timeout=%.0fs",
            self._model, len(prompt), num_predict, self._timeout,
        )

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

            data = resp.json()
            answer = data.get("response", "").strip()

            # If the answer looks truncated (ends mid-word), retry once with
            # a higher token limit so list queries don't get cut off.
            if answer and answer[-1] not in '.!?)"\'-•' and num_predict < 768:
                logger.warning(
                    "Answer may be truncated (last char=%r), retrying with "
                    "num_predict=%d", answer[-1], 768,
                )
                payload["options"]["num_predict"] = 768
                resp2 = await client.post(url, json=payload)
                resp2.raise_for_status()
                retry_answer = resp2.json().get("response", "").strip()
                if len(retry_answer) > len(answer):
                    answer = retry_answer

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        logger.info(
            "LLM synthesis OK: model=%s latency=%.1fms answer_chars=%d",
            self._model, elapsed_ms, len(answer),
        )
        return answer, round(elapsed_ms, 2)
