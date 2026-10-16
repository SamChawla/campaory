"""Deterministic fact guard (ADR-005, LLD 6.2).

Every URL, date, time, amount, handle and count in a post must come from a confirmed fact.
Anything else is flagged; flags other than RELATIVE_DATE block approval, as do placeholders.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.domain.facts import DateValue, Token, confirmed, extract_tokens, normalize_text
from app.domain.schemas import Fact, GuardFlag, Person

_PLACEHOLDER = re.compile(r"\[ADD: ([^\]]{1,60})\]")
_NUMBER = re.compile(r"\d[\d,]*")

_CODES = {
    "url": "UNKNOWN_URL",
    "date": "UNKNOWN_DATE",
    "time": "UNKNOWN_TIME",
    "amount": "UNKNOWN_AMOUNT",
    "handle": "UNKNOWN_HANDLE",
    "count": "UNKNOWN_COUNT",
}


@dataclass
class Allowed:
    urls: set[str] = field(default_factory=set)
    dates: set[DateValue] = field(default_factory=set)
    times: set[tuple[int, int]] = field(default_factory=set)
    amounts: set[tuple[str, Decimal]] = field(default_factory=set)
    handles: set[str] = field(default_factory=set)
    numbers: set[int] = field(default_factory=set)
    phrases: set[str] = field(default_factory=set)


def find_placeholders(text: str) -> list[str]:
    return [m.group(1) for m in _PLACEHOLDER.finditer(text)]


def is_blocking(flags: Iterable[GuardFlag], placeholders: Iterable[str]) -> bool:
    return any(f.blocking for f in flags) or any(True for _ in placeholders)


def check(text: str, facts: Iterable[Fact], *, extra_dates: Iterable[date] = ()) -> list[GuardFlag]:
    """Flag every fact-like token in text that no confirmed fact supports."""
    text = unicodedata.normalize("NFKC", text)
    allowed = build_allowed(facts, extra_dates)
    covered = _covered_spans(text, allowed.phrases)
    placeholder_spans = [m.span() for m in _PLACEHOLDER.finditer(text)]
    flags: list[GuardFlag] = []

    for token in extract_tokens(text):
        start, end = token.span
        if any(a <= start and end <= b for a, b in covered + placeholder_spans):
            continue
        if token.kind == "relative":
            flags.append(GuardFlag(code="RELATIVE_DATE", token=token.raw, span=token.span,
                                   blocking=False))  # fmt: skip
        elif not _is_allowed(token, allowed):
            flags.append(GuardFlag(code=_CODES[token.kind], token=token.raw, span=token.span))
    return flags


def build_allowed(facts: Iterable[Fact], extra_dates: Iterable[date] = ()) -> Allowed:
    allowed = Allowed()
    for f in confirmed(facts):
        values = f.value if isinstance(f.value, list) else [f.value]
        if f.key in ("speakers", "judges", "mentors", "partners", "hashtags", "handles"):
            allowed.numbers.add(len(values))
        for value in values:
            if isinstance(value, Person):
                _absorb(allowed, value.name, f.key)
                _absorb(allowed, value.role, f.key)
                if value.url:
                    _absorb(allowed, value.url, f.key)
                if value.handle:
                    allowed.handles.add("@" + value.handle.lstrip("@").lower())
            else:
                _absorb(allowed, value, f.key)
    for d in extra_dates:
        allowed.dates.add(DateValue(d.month, d.day, d.year))
    return allowed


def _absorb(allowed: Allowed, value: str, key: str) -> None:
    value = value.strip()
    if not value:
        return
    if key == "handles":
        allowed.handles.add("@" + value.lstrip("@").lower())
        return
    if len(value) >= 4 and not value.startswith("#"):
        allowed.phrases.add(normalize_text(value))
    allowed.numbers.update(int(n.replace(",", "")) for n in _NUMBER.findall(value))
    for token in extract_tokens(value):
        if token.kind == "url":
            allowed.urls.add(token.value)
        elif token.kind == "date":
            allowed.dates.add(token.value)
        elif token.kind == "time":
            allowed.times.add(token.value)
        elif token.kind == "amount":
            allowed.amounts.add(token.value)
        elif token.kind == "handle":
            allowed.handles.add(token.value)


def _is_allowed(token: Token, allowed: Allowed) -> bool:
    match token.kind:
        case "url":
            return token.value in allowed.urls
        case "date":
            d = token.value
            return any(
                a.month == d.month and a.day == d.day and (d.year is None or d.year == a.year)
                for a in allowed.dates
            )
        case "time":
            return token.value in allowed.times
        case "amount":
            return token.value[1] == 0 or token.value in allowed.amounts
        case "handle":
            return token.value in allowed.handles
        case "count":
            return token.value in allowed.numbers
    return False


def _covered_spans(text: str, phrases: set[str]) -> list[tuple[int, int]]:
    """Spans of text that repeat a confirmed fact verbatim (case and spacing ignored)."""
    if not phrases:
        return []
    folded, index = _fold_with_index(text)
    spans = []
    for phrase in phrases:
        for m in re.finditer(re.escape(phrase), folded):
            spans.append((index[m.start()], index[m.end() - 1] + 1))
    return spans


def _fold_with_index(text: str) -> tuple[str, list[int]]:
    """Casefold and collapse whitespace, keeping a map back to original offsets."""
    out: list[str] = []
    index: list[int] = []
    prev_space = True
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            index.append(i)
            prev_space = True
            continue
        for c in ch.casefold():
            out.append(c)
            index.append(i)
        prev_space = False
    return "".join(out), index
