"""Shapes the model must return. Lenient on extras; the API layer filters and normalises."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.schemas import MAX_POST_CHARS, Platform


class Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ExtractedFact(Loose):
    key: Annotated[str, Field(max_length=60)]
    value: str | int | float | list[Any]
    source_snippet: Annotated[str, Field(max_length=2000)] = ""


class ExtractOutput(Loose):
    facts: Annotated[list[ExtractedFact], Field(max_length=100)]


class GeneratedPost(Loose):
    platform: Platform
    text: Annotated[str, Field(min_length=1, max_length=MAX_POST_CHARS)]
    facts_used: list[str] = []


class GenerateOutput(Loose):
    posts: Annotated[list[GeneratedPost], Field(min_length=1, max_length=8)]


class RewrittenPost(Loose):
    text: Annotated[str, Field(min_length=1, max_length=MAX_POST_CHARS)]
    facts_used: list[str] = []
