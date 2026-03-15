"""Scoring helpers for AI exposure using OpenRouter.

Provides a thin wrapper around the OpenRouter chat-completions API with:
- retry behaviour for transient network/server errors
- graceful handling of malformed model responses
- failure recording so a batch run can continue past bad items
"""

import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Transient HTTP status codes that should trigger a retry
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Sentinel returned when a score cannot be produced even after retries
FAILURE_SENTINEL = "__failed__"


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n", 1)
        text = lines[1] if len(lines) > 1 else ""
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def score_occupation(
    client: httpx.Client,
    text: str,
    model: str,
    api_key: str,
    system_prompt: str,
    *,
    max_retries: int = 3,
    backoff: float = 2.0,
) -> dict[str, Any]:
    """Send one occupation to the LLM and return a parsed score dict.

    On success returns a dict with at least ``exposure`` and ``rationale``.
    On failure after all retries, returns ``{"error": "<reason>",
    "exposure": None}`` so callers can record the failure without crashing.

    Args:
        client: An ``httpx.Client`` instance (reused for connection pooling).
        text: The occupation Markdown to score.
        model: OpenRouter model identifier.
        api_key: OpenRouter API key.
        system_prompt: The scoring rubric / system prompt.
        max_retries: How many times to retry on transient failures.
        backoff: Base delay in seconds between retries (doubles each attempt).

    Returns:
        A dict with scoring data, or an error dict on total failure.
    """
    last_error: str = "unknown error"
    delay = backoff

    for attempt in range(1, max_retries + 1):
        try:
            response = client.post(
                API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.2,
                },
                timeout=60,
            )

            if response.status_code in _RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}"
                logger.warning(
                    "Attempt %d/%d retryable status %s", attempt, max_retries, last_error
                )
            else:
                response.raise_for_status()
                content = _strip_fences(response.json()["choices"][0]["message"]["content"])
                return json.loads(content)

        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Attempt %d/%d transient error: %s", attempt, max_retries, last_error)
        except json.JSONDecodeError as exc:
            last_error = f"JSON decode error: {exc}"
            logger.warning("Attempt %d/%d malformed response: %s", attempt, max_retries, last_error)
            # Malformed response is not a transient network issue — still retry
            # (model sometimes returns partial output) but with shorter wait.
        except httpx.HTTPStatusError as exc:
            # Non-retryable HTTP error (4xx other than 429)
            last_error = f"HTTP {exc.response.status_code}: {exc}"
            logger.error("Non-retryable HTTP error: %s", last_error)
            return {"error": last_error, "exposure": None}
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Attempt %d/%d unexpected error: %s", attempt, max_retries, last_error)

        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2

    logger.error("All %d attempts failed. Last error: %s", max_retries, last_error)
    return {"error": last_error, "exposure": None}
