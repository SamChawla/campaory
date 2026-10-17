"""Shared post-processing: every model-written post goes through the guard and the validators."""

from collections.abc import Iterable, Sequence
from dataclasses import asdict
from datetime import datetime

from fastapi import Response

from app.api.models import Meta, ValidationOut
from app.domain.facts import confirmed
from app.domain.guard import check, find_placeholders, is_blocking
from app.domain.platforms import validate
from app.domain.schemas import Fact, GuardFlag, Platform, PostStatus
from app.llm.base import LLMResult

PROVIDER_HEADER = "X-LLM-Provider"


def review(
    platform: Platform, text: str, facts: list[Fact], scheduled_for: datetime | None = None
) -> tuple[list[GuardFlag], list[str], ValidationOut, PostStatus]:
    extra = [scheduled_for.date()] if scheduled_for else []
    flags = check(text, facts, extra_dates=extra)
    placeholders = find_placeholders(text)
    validation = validate(platform, text)
    ok = validation.ok and not is_blocking(flags, placeholders)
    out = ValidationOut.model_validate(asdict(validation))
    return flags, placeholders, out, "draft" if ok else "needs_review"


def confirmed_keys(keys: Iterable[str], facts: list[Fact]) -> list[str]:
    """Keep only keys of confirmed facts, deduplicated, in the given order."""
    allowed = {f.key for f in confirmed(facts)}
    out: list[str] = []
    for key in keys:
        if key in allowed and key not in out:
            out.append(key)
    return out


def meta_for(results: Sequence[LLMResult]) -> Meta:
    providers = {r.provider for r in results}
    mock = "mock" in providers
    first = next((r for r in results if (r.provider == "mock") == mock), results[0])
    tokens_in = [r.input_tokens for r in results]
    tokens_out = [r.output_tokens for r in results]
    return Meta(
        provider=first.provider,
        model=first.model,
        prompt_version=first.prompt_version,
        latency_ms=max(r.latency_ms for r in results),
        input_tokens=None if None in tokens_in else sum(tokens_in),
        output_tokens=None if None in tokens_out else sum(tokens_out),
        is_mock=mock,
    )


def no_model_meta() -> Meta:
    return Meta(provider="none", model="", prompt_version="", latency_ms=0, is_mock=False)


def label_provider(response: Response, meta: Meta) -> None:
    response.headers[PROVIDER_HEADER] = meta.provider
