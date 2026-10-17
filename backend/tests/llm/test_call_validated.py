import logging

import pytest
from pydantic import BaseModel

from app.core.errors import AppError
from app.llm.base import Completion, LLMProvider, LLMUnavailable, call_validated
from app.llm.prompts import Prompt


class Answer(BaseModel):
    value: int


class ScriptedProvider:
    """Returns the given texts in order and records every prompt it saw."""

    name = "scripted"
    model = "scripted-1"

    def __init__(self, *texts: str | Exception) -> None:
        self._texts = list(texts)
        self.prompts: list[str] = []
        self.systems: list[str] = []

    async def complete(self, *, system, prompt, max_output_tokens=2048, temperature=0.4):
        self.systems.append(system)
        self.prompts.append(prompt)
        item = self._texts.pop(0)
        if isinstance(item, Exception):
            raise item
        return Completion(
            text=item,
            provider=self.name,
            model=self.model,
            latency_ms=100,
            input_tokens=10,
            output_tokens=5,
        )


PROMPT = Prompt(version="test.v1", system="SYSTEM", user="Give me a value.")


def test_scripted_provider_satisfies_protocol():
    assert isinstance(ScriptedProvider(), LLMProvider)


async def test_valid_fenced_output_is_parsed():
    provider = ScriptedProvider('```json\n{"value": 3}\n```')

    result = await call_validated(provider, PROMPT, Answer)

    assert result.data == Answer(value=3)
    assert result.provider == "scripted"
    assert result.model == "scripted-1"
    assert result.prompt_version == "test.v1"
    assert result.latency_ms == 100
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.attempts == 1
    assert provider.systems == ["SYSTEM"]


async def test_invalid_output_triggers_one_repair_prompt():
    provider = ScriptedProvider('{"value": "lots"}', '{"value": 4}')

    result = await call_validated(provider, PROMPT, Answer)

    assert result.data.value == 4
    assert result.attempts == 2
    assert len(provider.prompts) == 2
    repair = provider.prompts[1]
    assert repair.startswith(PROMPT.user)
    assert '{"value": "lots"}' in repair
    assert "value" in repair and "JSON" in repair
    assert result.latency_ms == 200
    assert result.input_tokens == 20
    assert result.output_tokens == 10


async def test_unparseable_output_is_repaired():
    provider = ScriptedProvider("I cannot do that.", '{"value": 1}')

    result = await call_validated(provider, PROMPT, Answer)

    assert result.data.value == 1


async def test_second_failure_raises_llm_invalid_output():
    provider = ScriptedProvider("nope", '{"value": "still wrong"}')

    with pytest.raises(AppError) as exc:
        await call_validated(provider, PROMPT, Answer)

    assert exc.value.status == 502
    assert exc.value.code == "llm_invalid_output"
    assert len(provider.prompts) == 2


async def test_extra_check_failure_is_repaired():
    def must_be_even(answer: Answer) -> None:
        if answer.value % 2:
            raise ValueError("value must be even")

    provider = ScriptedProvider('{"value": 3}', '{"value": 8}')

    result = await call_validated(provider, PROMPT, Answer, check=must_be_even)

    assert result.data.value == 8
    assert "value must be even" in provider.prompts[1]


async def test_unavailable_provider_error_propagates():
    provider = ScriptedProvider(LLMUnavailable())

    with pytest.raises(LLMUnavailable):
        await call_validated(provider, PROMPT, Answer)


async def test_token_counts_stay_none_when_provider_has_none():
    class NoUsage(ScriptedProvider):
        async def complete(self, **kwargs):
            done = await super().complete(**kwargs)
            return Completion(done.text, done.provider, done.model, 7, None, None)

    result = await call_validated(NoUsage('{"value": 1}'), PROMPT, Answer)

    assert result.input_tokens is None
    assert result.output_tokens is None


async def test_reports_provider_of_last_completion():
    class Switching(ScriptedProvider):
        async def complete(self, **kwargs):
            done = await super().complete(**kwargs)
            name = "mock" if len(self.prompts) == 2 else "euri"
            return Completion(done.text, name, name + "-model", 1, 1, 1)

    result = await call_validated(Switching("bad", '{"value": 2}'), PROMPT, Answer)

    assert result.provider == "mock"
    assert result.model == "mock-model"


async def test_log_line_has_metadata_but_no_text(caplog):
    provider = ScriptedProvider('{"value": 42}')
    prompt = Prompt(version="test.v1", system="SECRET SYSTEM", user="SECRET CAMPAIGN TEXT")

    with caplog.at_level(logging.INFO, logger="campaory.llm"):
        await call_validated(provider, prompt, Answer)

    lines = [r.getMessage() for r in caplog.records]
    assert len(lines) == 1
    line = lines[0]
    for part in ("provider=scripted", "model=scripted-1", "prompt_version=test.v1", "latency_ms="):
        assert part in line
    assert "input_tokens=10" in line and "output_tokens=5" in line
    assert "SECRET" not in line
    assert "42" not in line
