"""The campaign document (LLD section 3). One shape for localStorage, API bodies and DB import."""

import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

MAX_DOCUMENT_BYTES = 512 * 1024
MAX_POST_CHARS = 5000

Platform = Literal["linkedin", "instagram", "whatsapp", "x"]
PLATFORM_ORDER: tuple[Platform, ...] = ("linkedin", "instagram", "whatsapp", "x")
EventMode = Literal["online", "offline", "hybrid"]
Language = Literal["en", "hi", "hinglish"]
FactStatus = Literal["confirmed", "needs_review", "missing", "superseded"]
PostStatus = Literal["draft", "needs_review", "approved", "scheduled", "published"]
Stage = Literal["pre", "event", "post"]
SourceKind = Literal["url", "text", "sample", "manual"]

FactKey = Literal[
    "event_name",
    "event_type",
    "short_description",
    "start_date",
    "end_date",
    "start_time",
    "end_time",
    "timezone",
    "venue",
    "address",
    "city",
    "event_mode",
    "registration_url",
    "registration_status",
    "capacity",
    "registration_deadline",
    "audience",
    "speakers",
    "judges",
    "mentors",
    "partners",
    "hashtags",
    "handles",
    "language",
]

ShortText = Annotated[str, Field(max_length=2000)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Person(Strict):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    role: Annotated[str, Field(max_length=120)] = ""
    url: Annotated[str, Field(max_length=500)] | None = None
    handle: Annotated[str, Field(max_length=60)] | None = None


FactValue = str | list[Person] | list[Annotated[str, Field(max_length=200)]]


class Fact(Strict):
    id: UUID
    key: FactKey
    value: FactValue = ""
    status: FactStatus
    critical: bool
    source_snippet: ShortText | None = None
    source_ref: Annotated[str, Field(max_length=2000)] | None = None
    not_applicable: bool = False


class Source(Strict):
    kind: SourceKind
    url: Annotated[str, Field(max_length=2000)] | None = None
    fetched_at: AwareDatetime | None = None
    text_hash: Annotated[str, Field(max_length=80)] | None = None


class PlanItem(Strict):
    id: UUID
    title: Annotated[str, Field(min_length=1, max_length=120)]
    purpose: ShortText = ""
    stage: Stage
    scheduled_for: AwareDatetime | None = None
    position: Annotated[int, Field(ge=0)]
    fact_keys: list[FactKey] = []


class GuardFlag(Strict):
    code: Annotated[str, Field(max_length=40)]
    token: Annotated[str, Field(max_length=500)]
    span: tuple[int, int]
    blocking: bool = True


class PostVersion(Strict):
    id: UUID
    text: Annotated[str, Field(max_length=MAX_POST_CHARS)]
    reason: Annotated[str, Field(max_length=80)]
    created_at: AwareDatetime


class Post(Strict):
    id: UUID
    plan_item_id: UUID
    platform: Platform
    text: Annotated[str, Field(max_length=MAX_POST_CHARS)]
    status: PostStatus
    facts_used: list[FactKey] = []
    guard_flags: list[GuardFlag] = []
    placeholders: list[Annotated[str, Field(max_length=80)]] = []
    reminder_at: AwareDatetime | None = None
    published_url: Annotated[str, Field(max_length=2000)] | None = None
    published_at: AwareDatetime | None = None
    change_reason: Annotated[str, Field(max_length=300)] | None = None
    versions: list[PostVersion] = []


class CampaignDoc(Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal[1] = Field(1, alias="schema")
    id: UUID
    client_id: UUID
    version: Annotated[int, Field(ge=0)] = 0
    name: Annotated[str, Field(min_length=1, max_length=200)]
    event_mode: EventMode
    language: Language = "en"
    tone: Annotated[str, Field(max_length=40)] = ""
    platforms: Annotated[list[Platform], Field(min_length=1, max_length=4)]
    source: Source
    facts: Annotated[list[Fact], Field(max_length=100)] = []
    plan: Annotated[list[PlanItem], Field(max_length=40)] = []
    posts: Annotated[list[Post], Field(max_length=400)] = []
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("platforms")
    @classmethod
    def _unique_platforms(cls, value: list[Platform]) -> list[Platform]:
        if len(set(value)) != len(value):
            raise ValueError("platforms must be unique")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> "CampaignDoc":
        if self.client_id != self.id:
            raise ValueError("client_id must equal id")
        item_ids = {item.id for item in self.plan}
        for post in self.posts:
            if post.plan_item_id not in item_ids:
                raise ValueError(f"post {post.id} refers to an unknown plan item")
        return self


class DocumentTooLarge(ValueError):
    pass


def parse_document(raw: str | bytes) -> CampaignDoc:
    """Parse serialized JSON, enforcing the 512 KB cap before validation."""
    size = len(raw.encode() if isinstance(raw, str) else raw)
    if size > MAX_DOCUMENT_BYTES:
        raise DocumentTooLarge(f"document is {size} bytes; limit is {MAX_DOCUMENT_BYTES}")
    return CampaignDoc.model_validate(json.loads(raw))
