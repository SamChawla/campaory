"""Gemma through the Euri API (OpenAI-compatible chat completions)."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.core.config import Settings
from app.llm.base import Completion, LLMUnavailable

log = logging.getLogger("campaory.llm")

RETRY_BACKOFF_SECONDS = 1.0


class EuriProvider:
    name = "euri"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 45,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._timeout = timeout
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Settings) -> "EuriProvider":
        for field in ("euri_api_key", "euri_model"):
            if not getattr(settings, field):
                raise ValueError(f"{field.upper()} must be set when LLM_PROVIDER=euri")
        return cls(
            api_key=settings.euri_api_key,
            model=settings.euri_model,
            base_url=settings.euri_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_output_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> Completion:
        # Gemma has no system role in its chat template, so the system text leads the user turn.
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": f"{system}\n\n{prompt}"}],
            "max_tokens": max_output_tokens,
            "temperature": temperature,
        }
        started = time.monotonic()
        body = await self._post_with_retry(payload)
        latency_ms = int((time.monotonic() - started) * 1000)

        text = _first_message_text(body)
        usage = body.get("usage") or {}
        log.debug("llm http provider=%s model=%s latency_ms=%d", self.name, self.model, latency_ms)
        return Completion(
            text=text,
            provider=self.name,
            model=body.get("model") or self.model,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    async def _post_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in (1, 2):
                try:
                    response = await client.post(self._url, json=payload, headers=headers)
                except httpx.HTTPError as exc:
                    log.warning("llm %s network error: %s", self.name, type(exc).__name__)
                else:
                    if response.status_code < 400:
                        return _json_body(response)
                    log.warning("llm %s http %d", self.name, response.status_code)
                    if response.status_code < 500:
                        break
                if attempt == 1:
                    await self._sleep(RETRY_BACKOFF_SECONDS)
        raise LLMUnavailable()


def _json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise LLMUnavailable() from exc
    if not isinstance(body, dict):
        raise LLMUnavailable()
    return body


def _first_message_text(body: dict[str, Any]) -> str:
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMUnavailable() from exc
    if not isinstance(text, str):
        raise LLMUnavailable()
    return text
