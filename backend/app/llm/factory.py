"""Pick the provider from settings. The only place that decides which model serves a call."""

import logging

from app.core.config import Settings
from app.llm.base import Completion, LLMProvider, LLMUnavailable
from app.llm.euri import EuriProvider
from app.llm.mock import MockProvider

log = logging.getLogger("campaory.llm")


class FallbackProvider:
    """Real provider first; the mock answers only when the real one is unavailable.

    The completion keeps the provider that actually answered, so mock output is labelled mock.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.model = primary.model

    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_output_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> Completion:
        kwargs = dict(
            system=system,
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        try:
            return await self.primary.complete(**kwargs)
        except LLMUnavailable:
            log.warning("llm %s unavailable, falling back to %s", self.name, self.fallback.name)
            return await self.fallback.complete(**kwargs)


def get_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockProvider()
    primary = EuriProvider.from_settings(settings)
    if settings.llm_fallback_to_mock:
        return FallbackProvider(primary, MockProvider())
    return primary
