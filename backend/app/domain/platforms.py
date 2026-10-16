"""Platform limits and validators (LLD 6.3). Errors block approval (FR 11)."""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from app.domain.facts import extract_tokens
from app.domain.schemas import Platform

X_URL_LENGTH = 23
LIMITS: dict[Platform, int] = {"linkedin": 3000, "instagram": 2200, "whatsapp": 700, "x": 280}
LINKEDIN_READABLE = 1300
WHATSAPP_HARD = 4096
INSTAGRAM_MAX_HASHTAGS = 30

_HASHTAG = re.compile(r"(?<![\w&/#])#\w+")


@dataclass(frozen=True)
class Issue:
    level: Literal["error", "warning"]
    code: str
    message: str


@dataclass(frozen=True)
class Validation:
    ok: bool
    length: int
    limit: int
    hashtags: int
    issues: list[Issue] = field(default_factory=list)


def count_hashtags(text: str) -> int:
    url_spans = [t.span for t in extract_tokens(text) if t.kind == "url"]
    return sum(
        1 for m in _HASHTAG.finditer(text) if not any(a <= m.start() < b for a, b in url_spans)
    )


def measure(platform: Platform, text: str) -> int:
    text = unicodedata.normalize("NFC", text)
    if platform != "x":
        return len(text)
    length = len(text)
    for token in extract_tokens(text):
        if token.kind == "url":
            length += X_URL_LENGTH - (token.span[1] - token.span[0])
    return length


def validate(platform: Platform, text: str) -> Validation:
    limit = LIMITS[platform]
    length = measure(platform, text)
    hashtags = count_hashtags(text)
    issues: list[Issue] = []

    if not text.strip():
        issues.append(Issue("error", "empty", "The post is empty."))
    elif platform == "x" and length > limit:
        issues.append(Issue("error", "too_long", f"X allows {limit} characters; this is {length}."))
    elif platform == "linkedin":
        if length > limit:
            issues.append(Issue("error", "too_long", f"LinkedIn allows {limit} characters."))
        elif length > LINKEDIN_READABLE:
            issues.append(
                Issue(
                    "warning",
                    "long_for_readability",
                    f"Over {LINKEDIN_READABLE} characters, LinkedIn hides the rest behind "
                    '"see more".',
                )
            )
    elif platform == "instagram":
        if length > limit:
            issues.append(Issue("error", "too_long", f"Instagram allows {limit} characters."))
        if hashtags > INSTAGRAM_MAX_HASHTAGS:
            issues.append(
                Issue(
                    "error",
                    "too_many_hashtags",
                    f"Instagram allows {INSTAGRAM_MAX_HASHTAGS} hashtags; this has {hashtags}.",
                )
            )
        if any(t.kind == "url" for t in extract_tokens(text)):
            issues.append(
                Issue(
                    "warning",
                    "link_not_clickable",
                    'Links in Instagram captions are not clickable. Say "Link in bio" instead.',
                )
            )
    elif platform == "whatsapp":
        if length > WHATSAPP_HARD:
            issues.append(
                Issue("error", "too_long", f"WhatsApp allows {WHATSAPP_HARD} characters.")
            )
        elif length > limit:
            issues.append(
                Issue(
                    "warning",
                    "long_for_whatsapp",
                    f"Over {limit} characters is long for a forwarded message.",
                )
            )

    ok = not any(i.level == "error" for i in issues)
    return Validation(ok=ok, length=length, limit=limit, hashtags=hashtags, issues=issues)
