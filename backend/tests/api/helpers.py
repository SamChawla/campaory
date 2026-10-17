"""Test doubles shared by the API tests."""

from app.domain.schemas import Fact
from app.llm.base import Completion
from app.llm.mock import MockProvider


def facts_json(facts: list[Fact]) -> list[dict]:
    return [f.model_dump(mode="json") for f in facts]


class CapturingProvider(MockProvider):
    """Mock that records every prompt and can be told to misbehave on matching prompts."""

    def __init__(self, *, garbage_when: str | None = None, name: str = "mock") -> None:
        self.prompts: list[str] = []
        self.systems: list[str] = []
        self.garbage_when = garbage_when
        self.name = name

    async def complete(self, *, system, prompt, max_output_tokens=2048, temperature=0.4):
        self.systems.append(system)
        self.prompts.append(prompt)
        if self.garbage_when and self.garbage_when in prompt:
            return Completion("I would rather not.", self.name, self.model, 1, 1, 1)
        done = await super().complete(system=system, prompt=prompt)
        return Completion(
            done.text, self.name, done.model, done.latency_ms, done.input_tokens, done.output_tokens
        )
