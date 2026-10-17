"""Fact keys, the BR01 generation gate, and the normalisers shared by the guard and impact.

Pure functions only. Token extraction runs in a fixed order and masks what it has consumed,
so a date such as 24.10.2026 is never re-read as a time.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.schemas import Fact

CRITICAL_KEYS = frozenset(
    {
        "event_name",
        "start_date",
        "timezone",
        "event_mode",
        "registration_url",
        "audience",
        "language",
    }
)
GATE_KEYS = ("event_name", "start_date", "timezone", "audience", "language")
LIST_KEYS = frozenset({"speakers", "judges", "mentors", "partners", "hashtags", "handles"})
SUPPORTED_LANGUAGES = frozenset({"en", "hi", "hinglish"})


def is_critical(key: str) -> bool:
    return key in CRITICAL_KEYS


def is_filled(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def confirmed(facts: Iterable[Fact]) -> list[Fact]:
    return [f for f in facts if f.status == "confirmed"]


def confirmed_map(facts: Iterable[Fact]) -> dict[str, Fact]:
    return {f.key: f for f in confirmed(facts)}


def generation_blockers(facts: Iterable[Fact], language: str | None) -> list[str]:
    """Return the BR01 keys that are not confirmed with a usable value, in a stable order."""
    by_key = confirmed_map(facts)
    blockers: list[str] = []
    for key in GATE_KEYS:
        if key == "language":
            lang_fact = by_key.get("language")
            chosen = language or (lang_fact.value if lang_fact else None)
            if chosen not in SUPPORTED_LANGUAGES:
                blockers.append(key)
            continue
        fact = by_key.get(key)
        if fact is None or not is_filled(fact.value) or not _valid_value(key, fact.value):
            blockers.append(key)

    reg = by_key.get("registration_url")
    if not (reg and reg.not_applicable) and (
        reg is None or not isinstance(reg.value, str) or normalize_url(reg.value) is None
    ):
        blockers.append("registration_url")
    return blockers


def _valid_value(key: str, value: object) -> bool:
    if key == "start_date":
        return isinstance(value, str) and _iso_date(value) is not None
    if key == "timezone":
        return isinstance(value, str) and valid_timezone(value)
    return True


def _iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def valid_timezone(name: str) -> bool:
    if not re.fullmatch(r"[A-Za-z_]+(?:/[A-Za-z0-9_+\-]+)*", name.strip()):
        return False
    try:
        ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


# ---- text --------------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


# ---- tokens ------------------------------------------------------------------------------

TokenKind = Literal["url", "date", "time", "amount", "handle", "count", "relative"]


@dataclass(frozen=True)
class DateValue:
    month: int
    day: int
    year: int | None


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    raw: str
    span: tuple[int, int]
    value: object


_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_MONTH = (
    r"(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
)
_WEEKDAY = r"(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day|nesday|sday|urday|rsday)?"
_ORD = r"(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s+(?P<year>\d{4}))?"
_WD_PREFIX = rf"(?:{_WEEKDAY},?\s+)?"

_NUMERIC_DATE = r"(?P<day>\d{1,2})[/.\-](?P<m>\d{1,2})[/.\-](?P<year>\d{4}|\d{2})\b"
_DAY_MONTH = rf"(?P<day>\d{{1,2}}){_ORD}\s+(?:of\s+)?{_MONTH}(?![a-z]){_YEAR}"
_MONTH_DAY = rf"{_MONTH}\s+(?P<day>\d{{1,2}}){_ORD}\b{_YEAR}"

_DATE_PATTERNS = [
    re.compile(r"\b(?P<year>\d{4})-(?P<m>\d{2})-(?P<day>\d{2})\b"),
    re.compile(rf"\b{_WD_PREFIX}{_NUMERIC_DATE}", re.I),
    re.compile(rf"\b{_WD_PREFIX}{_DAY_MONTH}", re.I),
    re.compile(rf"\b{_WD_PREFIX}{_MONTH_DAY}", re.I),
]

_TIME_12 = re.compile(
    r"\b(?P<h>\d{1,2})(?:[:.](?P<min>[0-5]\d))?\s*(?P<ap>[ap])(?:\.\s?m\.|m\b)", re.I
)
_TIME_24 = re.compile(r"\b(?P<h>[01]?\d|2[0-3])[:.](?P<min>[0-5]\d)\b")

_CURRENCY = {
    "₹": "INR",
    "rs": "INR",
    "inr": "INR",
    "rupees": "INR",
    "$": "USD",
    "usd": "USD",
    "dollars": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
}
_NUM = r"(?P<num>\d[\d,]*(?:\.\d+)?)"
_AMOUNT_PATTERNS = [
    re.compile(rf"(?P<cur>₹|\$|€|£|\b(?:rs\.?|inr|usd|eur|gbp)(?![a-z]))\s?{_NUM}", re.I),
    re.compile(rf"\b{_NUM}\s?(?P<cur>rupees|inr|usd|dollars|eur|gbp)\b", re.I),
]

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"https?://[^\s<>\"'()\[\]]+", re.I)
_TLDS = r"com|org|net|io|dev|in|co|tech|ai|app|me|xyz|info|edu|gov|events|live|site"
_BARE_DOMAIN = re.compile(
    rf"(?<![\w@.\-/])(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:{_TLDS})\b(?:/[^\s<>\"'()\[\]]*)?",
    re.I,
)
_HANDLE = re.compile(r"(?<![\w@./])@(?P<name>[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,29}))")
_COUNT = re.compile(
    r"\b(?P<num>\d[\d,]*)\+?\s+(?P<noun>seats|spots|participants|people|attendees|speakers"
    r"|mentors|judges|teams|places|slots|hackers|developers|tickets)\b",
    re.I,
)
_RELATIVE = re.compile(
    r"\b(?:today|tonight|tomorrow|day after tomorrow|this weekend"
    r"|(?:this|next|coming)\s+(?:week|weekend|month|monday|tuesday|wednesday|thursday|friday"
    r"|saturday|sunday)"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)
_TRAILING = ".,;:!?"


def _date_from_match(m: re.Match[str]) -> DateValue | None:
    groups = m.groupdict()
    if groups.get("mon"):
        month = _MONTHS[groups["mon"][:3].lower()]
    else:
        month = int(groups["m"])
    day = int(groups["day"])
    year_raw = groups.get("year")
    year = None
    if year_raw:
        year = int(year_raw) + (2000 if len(year_raw) == 2 else 0)
    try:
        date(year or 2024, month, day)
    except ValueError:
        return None
    return DateValue(month, day, year)


def _time_from_match(m: re.Match[str], twelve: bool) -> tuple[int, int] | None:
    hour = int(m.group("h"))
    minute = int(m.group("min") or 0)
    if twelve:
        if not 1 <= hour <= 12:
            return None
        pm = m.group("ap").lower() == "p"
        hour = (hour % 12) + (12 if pm else 0)
    return (hour, minute)


def _amount_from_match(m: re.Match[str]) -> tuple[str, Decimal] | None:
    cur = m.group("cur").lower().rstrip(".")
    try:
        return (_CURRENCY[cur], Decimal(m.group("num").replace(",", "")))
    except (KeyError, InvalidOperation):
        return None


def extract_tokens(text: str) -> list[Token]:
    """Find every fact-like token in text, ordered by position."""
    text = unicodedata.normalize("NFKC", text)
    taken: list[tuple[int, int]] = []
    tokens: list[Token] = []

    def free(start: int, end: int) -> bool:
        return all(end <= a or start >= b for a, b in taken)

    def add(kind: TokenKind, start: int, end: int, value: object) -> None:
        taken.append((start, end))
        tokens.append(Token(kind, text[start:end], (start, end), value))

    for m in _EMAIL.finditer(text):
        taken.append(m.span())

    for pattern in (_URL, _BARE_DOMAIN):
        for m in pattern.finditer(text):
            start, end = m.span()
            while end > start and text[end - 1] in _TRAILING:
                end -= 1
            if free(start, end):
                norm = normalize_url(text[start:end])
                if norm:
                    add("url", start, end, norm)

    for pattern in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            value = _date_from_match(m)
            if value and free(*m.span()):
                add("date", *m.span(), value)

    for pattern in _AMOUNT_PATTERNS:
        for m in pattern.finditer(text):
            value = _amount_from_match(m)
            if value and free(*m.span()):
                add("amount", *m.span(), value)

    for pattern, twelve in ((_TIME_12, True), (_TIME_24, False)):
        for m in pattern.finditer(text):
            value = _time_from_match(m, twelve)
            if value and free(*m.span()):
                add("time", *m.span(), value)

    for m in _HANDLE.finditer(text):
        start, end = m.span()
        while text[end - 1] == ".":
            end -= 1
        if free(start, end):
            add("handle", start, end, text[start:end].lower())

    for m in _COUNT.finditer(text):
        if free(*m.span()):
            add("count", *m.span(), int(m.group("num").replace(",", "")))

    for m in _RELATIVE.finditer(text):
        if free(*m.span()):
            add("relative", *m.span(), m.group(0).lower())

    return sorted(tokens, key=lambda t: t.span)


def _first(text: str, kind: TokenKind) -> object | None:
    for token in extract_tokens(text):
        if token.kind == kind:
            return token.value
    return None


def parse_date(text: str) -> DateValue | None:
    value = _first(text, "date")
    return value if isinstance(value, DateValue) else None


def parse_time(text: str) -> tuple[int, int] | None:
    value = _first(text, "time")
    return value if isinstance(value, tuple) else None


def parse_amount(text: str) -> tuple[str, Decimal] | None:
    value = _first(text, "amount")
    return value if isinstance(value, tuple) else None


_HOST = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}")


def normalize_url(raw: str) -> str | None:
    """Scheme-less, lower-case host without www, no trailing slash, utm_* dropped."""
    raw = raw.strip().rstrip(_TRAILING)
    if not raw or any(c.isspace() for c in raw):
        return None
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        raw = "http://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower()
    host = host.removeprefix("www.")
    if not _HOST.fullmatch(host):
        return None
    if parts.port:
        host = f"{host}:{parts.port}"
    path = parts.path.rstrip("/")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
    ]
    out = host + path
    if query:
        out += "?" + urlencode(query)
    return out


def long_date(iso: str) -> str | None:
    """`2026-10-24` as `Saturday, 24 October 2026`; None if not an ISO date."""
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return f"{d:%A}, {d.day} {d:%B %Y}"
