"""Request and response bodies of the stateless endpoints (LLD 5.1 to 5.7)."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.domain.schemas import (
    Fact,
    FactKey,
    FactStatus,
    FactValue,
    GuardFlag,
    Language,
    PlanItem,
    Platform,
    Post,
    PostStatus,
    Source,
    Stage,
    Strict,
)

MAX_ITEMS_PER_GENERATE = 4
Facts = Annotated[list[Fact], Field(max_length=100)]
Platforms = Annotated[list[Platform], Field(min_length=1, max_length=4)]
PostText = Annotated[str, Field(max_length=5000)]


class Meta(BaseModel):
    provider: str
    model: str
    prompt_version: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    is_mock: bool


class IssueOut(BaseModel):
    level: Literal["error", "warning"]
    code: str
    message: str


class ValidationOut(BaseModel):
    ok: bool
    length: int
    limit: int
    hashtags: int
    issues: list[IssueOut]


# ---- brief ------------------------------------------------------------------------------


class UrlSource(Strict):
    kind: Literal["url"]
    url: Annotated[str, Field(min_length=1, max_length=2000)]


class TextSource(Strict):
    kind: Literal["text"]
    text: str


class SampleSource(Strict):
    kind: Literal["sample"]


class ExtractRequest(Strict):
    source: Annotated[UrlSource | TextSource | SampleSource, Field(discriminator="kind")]


class CandidateFact(BaseModel):
    key: FactKey
    value: FactValue
    status: FactStatus
    critical: bool
    source_snippet: str | None
    source_ref: str | None


class ExtractResponse(BaseModel):
    facts: list[CandidateFact]
    source: Source
    warnings: list[str]
    meta: Meta


# ---- plan -------------------------------------------------------------------------------


class PlanRequest(Strict):
    facts: Facts
    platforms: Platforms
    today: date | None = None
    timezone: Annotated[str, Field(max_length=64)] | None = None
    language: Language = "en"


class ProposedItemOut(BaseModel):
    title: str
    purpose: str
    stage: Stage
    scheduled_for: datetime
    fact_keys: list[str]
    platforms: list[Platform]


class PlanResponse(BaseModel):
    items: list[ProposedItemOut]


# ---- posts ------------------------------------------------------------------------------


class GenerateItem(Strict):
    id: UUID
    title: Annotated[str, Field(min_length=1, max_length=120)]
    purpose: Annotated[str, Field(max_length=2000)] = ""
    stage: Stage
    fact_keys: list[FactKey] = []
    scheduled_for: AwareDatetime | None = None


class GenerateRequest(Strict):
    facts: Facts
    language: Language = "en"
    tone: Annotated[str, Field(max_length=40)] = ""
    items: Annotated[list[GenerateItem], Field(min_length=1, max_length=MAX_ITEMS_PER_GENERATE)]
    platforms: Platforms


class CheckedPost(BaseModel):
    plan_item_id: UUID
    platform: Platform
    text: str
    facts_used: list[str]
    status: PostStatus
    guard_flags: list[GuardFlag]
    placeholders: list[str]
    validation: ValidationOut


class FailedItem(BaseModel):
    plan_item_id: UUID
    error: str


class GenerateResponse(BaseModel):
    posts: list[CheckedPost]
    failed: list[FailedItem]
    meta: Meta


class PostInput(Strict):
    platform: Platform
    text: PostText
    facts_used: list[FactKey] = []
    status: PostStatus | None = None
    scheduled_for: AwareDatetime | None = None


Instruction = Literal["make_shorter", "make_longer", "warmer", "more_formal", "custom"]


class ReviseRequest(Strict):
    facts: Facts
    post: PostInput
    instruction: Instruction
    custom_instruction: Annotated[str, Field(max_length=200)] = ""

    @model_validator(mode="after")
    def _custom_needs_text(self) -> "ReviseRequest":
        if self.instruction == "custom" and not self.custom_instruction.strip():
            raise ValueError("custom_instruction is required when instruction is custom")
        return self


class RewriteResponse(BaseModel):
    text: str
    facts_used: list[str]
    guard_flags: list[GuardFlag]
    placeholders: list[str]
    validation: ValidationOut
    status: PostStatus
    meta: Meta


class ValidateRequest(Strict):
    platform: Platform
    text: PostText
    facts: Facts
    scheduled_for: AwareDatetime | None = None


class ValidateResponse(BaseModel):
    validation: ValidationOut
    guard_flags: list[GuardFlag]
    placeholders: list[str]


# ---- impact -----------------------------------------------------------------------------


class Changed(Strict):
    key: FactKey
    old: FactValue
    new: FactValue


class AnalyzeRequest(Strict):
    changed: Changed
    facts: Facts
    posts: Annotated[list[Post], Field(max_length=400)]
    plan: Annotated[list[PlanItem], Field(max_length=40)]
    today: date | None = None
    language: Language = "en"


class AffectedOut(BaseModel):
    post_id: UUID
    reason: Literal["facts_used", "text_match", "plan_item"]
    detail: str


class ProtectedOut(BaseModel):
    post_id: UUID
    status: str
    note: str


class PlanChangeOut(BaseModel):
    plan_item_id: UUID
    field: str
    old: datetime | None
    new: datetime


class AnalyzeResponse(BaseModel):
    affected: list[AffectedOut]
    protected: list[ProtectedOut]
    plan_changes: list[PlanChangeOut]


class RedraftRequest(Strict):
    changed: Changed
    facts: Facts
    post: Post
    scheduled_for: AwareDatetime | None = None


class SpanOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str


class RedraftResponse(BaseModel):
    proposed_text: str
    changed_spans: list[SpanOut]
    reason: str
    facts_used: list[str]
    guard_flags: list[GuardFlag]
    placeholders: list[str]
    validation: ValidationOut
    status: PostStatus
    meta: Meta
