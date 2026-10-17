"""Model access for the stateless endpoints: rate limits, the daily cap and the mock fallback."""

from typing import Annotated

from fastapi import Depends, FastAPI, Request

from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import DailyCap, LimitSubject, RateLimiter, limit_subject, model_rules
from app.fetch.safe_fetch import safe_fetch
from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.llm.mock import MockProvider


class ModelGate:
    """Charges one model call to a subject and says which provider serves it."""

    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        *,
        limiter: RateLimiter,
        cap: DailyCap,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.limiter = limiter
        self.cap = cap
        self.mock = MockProvider()

    def acquire(self, subject: LimitSubject) -> LLMProvider:
        self.limiter.hit(subject.key, model_rules(self.settings, subject))
        if self.provider.name == "mock" or self.cap.take():
            return self.provider
        if self.settings.llm_fallback_to_mock:
            return self.mock
        raise AppError(
            503, "llm_unavailable", "The daily model limit is reached. Try again tomorrow."
        )


def install_ai(app: FastAPI, settings: Settings) -> None:
    limiter = RateLimiter()
    app.state.limiter = limiter
    app.state.gate = ModelGate(
        settings, get_provider(settings), limiter=limiter, cap=DailyCap(settings.llm_daily_cap)
    )
    app.state.fetch_page = safe_fetch


class ModelAccess:
    """Lazily charges the caller; endpoints call `provider()` right before the model call."""

    def __init__(self, gate: ModelGate, subject: LimitSubject) -> None:
        self._gate = gate
        self._subject = subject

    def provider(self) -> LLMProvider:
        return self._gate.acquire(self._subject)


def model_access(
    request: Request, subject: Annotated[LimitSubject, Depends(limit_subject)]
) -> ModelAccess:
    return ModelAccess(request.app.state.gate, subject)


Model = Annotated[ModelAccess, Depends(model_access)]
