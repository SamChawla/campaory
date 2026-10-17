from dataclasses import dataclass

from app.core.errors import AppError


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None


class LLMUnavailable(AppError):
    def __init__(self, message: str = "The writing model is not available right now.") -> None:
        super().__init__(502, "llm_unavailable", message)
