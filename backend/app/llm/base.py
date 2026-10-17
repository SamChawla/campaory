"""Provider interface and the validated call wrapper (LLD 6.5).

Providers return raw text. `call_validated` owns JSON extraction, schema validation and the
single repair attempt, so every provider behaves the same.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from app.core.errors import AppError
from app.llm.jsonrepair import JSONExtractionError, extract_json_object
from app.llm.prompts import Prompt, repair_prompt

log = logging.getLogger("campaory.llm")


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_output_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> Completion: ...


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    data: T
    provider: str
    model: str
    prompt_version: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    attempts: int


class LLMUnavailable(AppError):
    def __init__(self, message: str = "The writing model is not available right now.") -> None:
        super().__init__(502, "llm_unavailable", message)


class LLMInvalidOutput(AppError):
    def __init__(self) -> None:
        super().__init__(
            502, "llm_invalid_output", "The writing model returned something unusable. Try again."
        )


async def call_validated[T: BaseModel](
    provider: LLMProvider,
    prompt: Prompt,
    schema: type[T],
    *,
    check: Callable[[T], None] | None = None,
    max_output_tokens: int = 2048,
    temperature: float = 0.4,
) -> LLMResult[T]:
    """Call the provider, parse and validate JSON, repair once, else raise llm_invalid_output."""
    completions: list[Completion] = []
    user = prompt.user
    data: T | None = None
    for attempt in (1, 2):
        done = await provider.complete(
            system=prompt.system,
            prompt=user,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        completions.append(done)
        try:
            data = _parse(done.text, schema, check)
            break
        except _Invalid as exc:
            if attempt == 1:
                user = repair_prompt(prompt, done.text, str(exc), _schema_text(schema))

    last = completions[-1]
    result_meta = dict(
        provider=last.provider,
        model=last.model,
        prompt_version=prompt.version,
        latency_ms=sum(c.latency_ms for c in completions),
        input_tokens=_sum(c.input_tokens for c in completions),
        output_tokens=_sum(c.output_tokens for c in completions),
        attempts=len(completions),
    )
    log.info(
        "llm call provider=%s model=%s prompt_version=%s latency_ms=%d input_tokens=%s "
        "output_tokens=%s attempts=%d ok=%s",
        result_meta["provider"],
        result_meta["model"],
        result_meta["prompt_version"],
        result_meta["latency_ms"],
        result_meta["input_tokens"],
        result_meta["output_tokens"],
        result_meta["attempts"],
        data is not None,
    )
    if data is None:
        raise LLMInvalidOutput()
    return LLMResult(data=data, **result_meta)


class _Invalid(ValueError):
    pass


def _parse[T: BaseModel](text: str, schema: type[T], check: Callable[[T], None] | None) -> T:
    try:
        data = schema.model_validate(extract_json_object(text))
    except JSONExtractionError as exc:
        raise _Invalid(str(exc)) from exc
    except ValidationError as exc:
        raise _Invalid(_describe(exc)) from exc
    if check is not None:
        try:
            check(data)
        except ValueError as exc:
            raise _Invalid(str(exc)) from exc
    return data


def _describe(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors(include_input=False, include_url=False)[:10]:
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


def _schema_text(schema: type[BaseModel]) -> str:
    return json.dumps(schema.model_json_schema(), separators=(",", ":"))


def _sum(values) -> int | None:
    values = list(values)
    if any(v is None for v in values):
        return None
    return sum(values)
