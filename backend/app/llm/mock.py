"""Deterministic stand-in for the model (LLD 6.5). No network.

It reads the task marker and data blocks from the prompt, so it exercises the same prompt and
validation path as the real provider. Output is labelled provider "mock" so the UI can show
the "Demo model" badge; it is never presented as Gemma.
"""

import json
import re
from datetime import date
from typing import Any

from app.domain.facts import extract_tokens, parse_time
from app.domain.platforms import measure
from app.llm.base import Completion
from app.llm.prompts import (
    EXTRACT_VERSION,
    GENERATE_VERSION,
    REDRAFT_VERSION,
    REVISE_VERSION,
    block,
    json_block,
    task_of,
)

MOCK_MODEL = "campaory-mock-1"


class MockProvider:
    name = "mock"
    model = MOCK_MODEL

    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_output_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> Completion:
        task = task_of(prompt)
        if task == EXTRACT_VERSION:
            body: dict[str, Any] = {"facts": extract_facts(block(prompt, "source") or "")}
        elif task == GENERATE_VERSION:
            body = _generate(prompt)
        elif task == REVISE_VERSION:
            body = _revise(prompt)
        elif task == REDRAFT_VERSION:
            body = _redraft(prompt)
        else:
            body = {}
        text = "```json\n" + json.dumps(body, ensure_ascii=False) + "\n```"
        return Completion(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=0,
            input_tokens=len(prompt) // 4,
            output_tokens=len(text) // 4,
        )


# ---- extract ------------------------------------------------------------------------------

_TIMEZONES = {"IST": "Asia/Kolkata", "UTC": "UTC", "GMT": "UTC"}
_IANA = re.compile(r"\b(?:Asia|Europe|America|Africa|Australia|Pacific)/[A-Za-z_]+\b")
_ABBR_TZ = re.compile(r"\b(IST|UTC|GMT)\b")
_LABEL = re.compile(r"^\s*([A-Za-z][A-Za-z '/-]{1,40}?)\s*:\s*(.+?)\s*$")
_PEOPLE_LABELS = {
    "speaker": "speakers",
    "speakers": "speakers",
    "mentor": "mentors",
    "mentors": "mentors",
    "judge": "judges",
    "judges": "judges",
    "partner": "partners",
    "partners": "partners",
    "sponsor": "partners",
    "sponsors": "partners",
}
_AUDIENCE_LABELS = {"who should come", "audience", "who can attend", "open to", "for whom"}
_EVENT_TYPE = re.compile(r"\b(hack ?day|hackathon|meetup|workshop|conference|bootcamp)\b", re.I)
_DEADLINE = re.compile(r"\b(?:closes|closing|deadline|register by|last date)\b[:\s]*", re.I)
_MODES = [
    (re.compile(r"\bhybrid\b", re.I), "hybrid"),
    (re.compile(r"\b(?:in person|in-person|offline)\b", re.I), "offline"),
    (re.compile(r"\b(?:online|virtual)\b", re.I), "online"),
]
_STATUS = re.compile(r"\b(free entry|registrations? (?:are |is )?(?:open|closed)|waitlist)\b", re.I)
_URL = re.compile(r"https?://[^\s<>\"'()\[\]]+")
_HASHTAG = re.compile(r"(?<![\w&/#])#\w+")


def extract_facts(text: str) -> list[dict[str, Any]]:
    """Regex extraction over plain text. Every snippet is an exact substring of the text."""
    facts: dict[str, dict[str, Any]] = {}

    def put(key: str, value: Any, snippet: str) -> None:
        if key not in facts and value not in ("", [], None):
            facts[key] = {"key": key, "value": value, "source_snippet": snippet}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    labelled = [(m.group(1).strip().lower(), m.group(2)) for m in map(_LABEL.match, lines) if m]

    for line in lines:
        if _is_title(line):
            put("event_name", line, line)
            break

    tokens = extract_tokens(text)
    deadline = _deadline(text)
    dates = [t for t in tokens if t.kind == "date" and t.value.year]
    for t in dates:
        if deadline and t.span == deadline.span:
            continue
        put("start_date", _iso(t.value), t.raw)
        break
    if deadline:
        put("registration_deadline", _iso(deadline.value), deadline.raw)

    times = [t for t in tokens if t.kind == "time"]
    if times:
        put("start_time", "{:02d}:{:02d}".format(*times[0].value), times[0].raw)
    if len(times) > 1:
        put("end_time", "{:02d}:{:02d}".format(*times[1].value), times[1].raw)

    if m := _IANA.search(text):
        put("timezone", m.group(0), m.group(0))
    elif m := _ABBR_TZ.search(text):
        put("timezone", _TIMEZONES[m.group(1)], m.group(1))

    for label, value in labelled:
        if label == "venue":
            parts = [p.strip() for p in value.split(",")]
            put("venue", parts[0], parts[0])
            if len(parts) > 1:
                rest = value[len(value.split(",")[0]) + 1 :].strip()
                put("address", rest, rest)
                put("city", parts[-1], parts[-1])
        elif label in ("address",):
            put("address", value, value)
        elif label == "city":
            put("city", value, value)
        elif label in _AUDIENCE_LABELS:
            audience = value.rstrip(".")
            put("audience", audience, audience)
        elif label in _PEOPLE_LABELS:
            put(_PEOPLE_LABELS[label], _people(value), value)
        elif label in ("handles", "follow"):
            handles = re.findall(r"@\w+", value)
            put("handles", handles, value)
        elif label in ("hashtags", "tags"):
            put("hashtags", _HASHTAG.findall(value), value)

    for pattern, mode in _MODES:
        if m := pattern.search(text):
            put("event_mode", mode, m.group(0))
            break

    if m := _URL.search(text):
        url = m.group(0).rstrip(".,;:!?")
        put("registration_url", url, url)
    if m := _STATUS.search(text):
        put("registration_status", m.group(0)[0].upper() + m.group(0)[1:], m.group(0))
    for t in tokens:
        if t.kind == "count" and re.search(r"seats|spots|participants|places|tickets", t.raw, re.I):
            put("capacity", str(t.value), t.raw)
            break
    if m := _EVENT_TYPE.search(text):
        put("event_type", m.group(0), m.group(0))
    tags = _HASHTAG.findall(text)
    if tags:
        put("hashtags", tags, tags[0])

    order = [
        "event_name",
        "event_type",
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
    ]
    return [facts[k] for k in order if k in facts]


def _is_title(line: str) -> bool:
    return (
        ":" not in line
        and not line.endswith(".")
        and len(line.split()) <= 12
        and not line.isupper()
        and not any(t.kind in ("date", "time", "url") for t in extract_tokens(line))
    )


def _deadline(text: str):
    for m in _DEADLINE.finditer(text):
        for t in extract_tokens(text[m.end() : m.end() + 40]):
            if t.kind == "date" and t.value.year and t.span[0] == 0:
                start = m.end()
                return type(t)(t.kind, t.raw, (start, start + len(t.raw)), t.value)
    return None


def _iso(value) -> str:
    return date(value.year, value.month, value.day).isoformat()


def _people(value: str) -> list[dict[str, str]]:
    people = []
    for part in _split_outside_parens(value):
        m = re.fullmatch(r"(.+?)\s*\(([^)]*)\)", part)
        name, extra = (m.group(1), m.group(2).strip()) if m else (part, "")
        person = {"name": name.strip(), "role": ""}
        if extra.startswith("@"):
            person["handle"] = extra
        else:
            person["role"] = extra
        if person["name"]:
            people.append(person)
    return people


def _split_outside_parens(value: str) -> list[str]:
    parts, depth, current = [], 0, ""
    for ch in value:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    out = []
    for part in parts:
        out.extend(p for p in re.split(r"\s+and\s+(?![^(]*\))", part.strip()) if p)
    return [p.strip() for p in out if p.strip()]


# ---- generate -----------------------------------------------------------------------------

_OPENERS = [
    ("Event announcement", "Announcing {name}!"),
    ("Why attend", "Why join {name}?"),
    ("Meet the", "Meet the people at {name}."),
    ("Partner announcement", "{name} has great partners."),
    ("Registration update", "Registration update for {name}."),
    ("Participant preparation", "Getting ready for {name}."),
    ("Final registration reminder", "Last call to register for {name}."),
    ("Event-day live update", "{name} is live now!"),
    ("Post-event thank-you", "Thank you for joining {name}!"),
    ("Highlights", "Highlights from {name}."),
]


def long_date(iso: str) -> str | None:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return f"{d:%A}, {d.day} {d:%B %Y}"


def short_date(iso: str) -> str | None:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return f"{d.day} {d:%b}"


def clock(value: str) -> str:
    parsed = parse_time(value) if isinstance(value, str) else None
    if not parsed:
        return str(value)
    h, m = parsed
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


class _Facts:
    """Read-side helper over the confirmed facts JSON from the prompt."""

    def __init__(self, facts: dict[str, Any], keys: list[str]) -> None:
        self.all = facts
        self.allowed = set(keys) | {"event_name"} if keys else set(facts)
        self.used: list[str] = []

    def get(self, key: str) -> Any:
        if key not in self.allowed or key not in self.all:
            return None
        if key not in self.used:
            self.used.append(key)
        return self.all[key]

    def peek(self, key: str) -> Any:
        return self.all.get(key) if key in self.allowed else None


def _opener(title: str, name: str) -> str:
    for prefix, template in _OPENERS:
        if title.startswith(prefix):
            return template.format(name=name)
    return f"{title}: {name}"


def _when(f: _Facts, short: bool = False) -> str:
    parts = []
    start = f.get("start_date")
    if start:
        parts.append((short_date if short else long_date)(start) or start)
    if f.peek("start_time"):
        t = clock(f.get("start_time"))
        if f.peek("end_time"):
            t += " to " + clock(f.get("end_time"))
        parts.append(t)
    return ", ".join(parts)


def _where(f: _Facts) -> str:
    mode = f.peek("event_mode")
    venue = f.get("venue")
    address = f.get("address")
    city = None if address else f.get("city")
    place = ", ".join(p for p in (venue, address, city) if p)
    if mode == "online":
        f.get("event_mode")
        return "Online" + (f" and at {place}" if place else "")
    if mode == "hybrid":
        f.get("event_mode")
        return (place + " and online") if place else "Online and in person"
    return place


def _people_line(f: _Facts) -> str:
    out = []
    for key, label in (("speakers", "Speakers"), ("mentors", "Mentors"), ("judges", "Judges")):
        people = f.get(key)
        if people:
            names = ", ".join(
                p["name"] + (f" ({p['role']})" if p.get("role") else "") for p in people
            )
            out.append(f"{label}: {names}.")
    return " ".join(out)


def _partners_line(f: _Facts) -> str:
    partners = f.get("partners")
    if not partners:
        return ""
    names = []
    for p in partners:
        handle = p.get("handle")
        names.append(p["name"] + (f" (@{handle.lstrip('@')})" if handle else ""))
    return "Thanks to our partners " + ", ".join(names) + "."


def _registration(f: _Facts) -> tuple[str, str | None]:
    bits = []
    status = f.get("registration_status")
    if status:
        bits.append(status.rstrip(".") + ".")
    capacity = f.get("capacity")
    if capacity and str(capacity).isdigit():
        bits.append(f"Limited to {capacity} seats.")
    deadline = f.get("registration_deadline")
    if deadline:
        bits.append(f"Register by {long_date(deadline) or deadline}.")
    return " ".join(bits), f.get("registration_url")


def _hashtags(f: _Facts, limit: int | None = None) -> str:
    tags = f.get("hashtags") or []
    return " ".join(tags[:limit] if limit else tags)


def _linkedin(title: str, f: _Facts) -> str:
    name = f.get("event_name")
    lines = [_opener(title, name)]
    detail = " | ".join(p for p in (_when(f), _where(f)) if p)
    if detail:
        lines.append(detail)
    audience = f.get("audience")
    if audience:
        lines.append(f"Who it is for: {audience}.")
    description = f.get("short_description")
    if description:
        lines.append(description)
    for line in (_people_line(f), _partners_line(f)):
        if line:
            lines.append(line)
    reg, url = _registration(f)
    if reg:
        lines.append(reg)
    if url:
        lines.append(f"Register here: {url}")
    tags = _hashtags(f)
    if tags:
        lines.append(tags)
    return "\n\n".join(lines)


def _instagram(title: str, f: _Facts) -> str:
    name = f.get("event_name")
    lines = [_opener(title, name), ""]
    when, where = _when(f), _where(f)
    if when:
        lines.append(when)
    if where:
        lines.append(where)
    audience = f.get("audience")
    if audience:
        lines.append(f"For {audience}.")
    people = _people_line(f)
    if people:
        lines.append(people)
    if f.peek("registration_url"):
        f.get("registration_url")
        lines.append("Link in bio.")
    tags = _hashtags(f)
    if tags:
        lines += ["", tags]
    lines += ["---", f"Image text: {name}"]
    return "\n".join(lines)


def _whatsapp(title: str, f: _Facts) -> str:
    name = f.get("event_name")
    lines = ["Hi! " + _opener(title, name)]
    when, where = _when(f), _where(f)
    if when:
        lines.append(f"When: {when}")
    if where:
        lines.append(f"Where: {where}")
    reg, url = _registration(f)
    if reg:
        lines.append(reg)
    if url:
        lines.append(f"Register: {url}")
    lines.append("Please share with anyone who would enjoy it.")
    return "\n".join(lines)


def _x(title: str, f: _Facts) -> str:
    name = f.get("event_name")
    used_before = list(f.used)
    parts = {
        "head": _opener(title, name),
        "when": _when(f, short=True),
        "city": f.get("city") or "",
        "url": f.get("registration_url") or "",
        "tags": _hashtags(f, 2),
    }

    def render() -> str:
        head = parts["head"]
        detail = ", ".join(p for p in (parts["when"], parts["city"]) if p)
        body = " ".join(p for p in (head, detail + "." if detail else "") if p)
        return "\n".join(p for p in (body, parts["url"], parts["tags"]) if p)

    for drop in ("tags", "city", "when"):
        if measure("x", render()) <= 280:
            break
        parts[drop] = ""
    text = render()
    if measure("x", text) > 280:
        text = text[:270].rsplit(" ", 1)[0]
    f.used = [k for k in f.used if k in used_before or _still_used(k, parts)]
    return text


def _still_used(key: str, parts: dict[str, str]) -> bool:
    return {
        "hashtags": bool(parts["tags"]),
        "city": bool(parts["city"]),
        "start_date": bool(parts["when"]),
        "start_time": bool(parts["when"]),
        "end_time": bool(parts["when"]),
        "registration_url": bool(parts["url"]),
    }.get(key, True)


_WRITERS = {"linkedin": _linkedin, "instagram": _instagram, "whatsapp": _whatsapp, "x": _x}


def _generate(prompt: str) -> dict[str, Any]:
    facts = json_block(prompt, "facts") or {}
    item = json_block(prompt, "item") or {}
    platforms = json_block(prompt, "platforms") or []
    if "event_name" not in facts:
        return {"posts": []}
    posts = []
    for platform in platforms:
        f = _Facts(facts, list(item.get("fact_keys") or []))
        text = _WRITERS[platform](str(item.get("title") or ""), f)
        posts.append({"platform": platform, "text": text, "facts_used": f.used})
    return {"posts": posts}


# ---- revise and redraft -------------------------------------------------------------------


def _facts_in(text: str, facts: dict[str, Any]) -> list[str]:
    """Keys whose value (or a rendering of it) appears in the text."""
    lowered = text.lower()
    used = []
    for key, value in facts.items():
        values = value if isinstance(value, list) else [value]
        forms: list[str] = []
        for v in values:
            if isinstance(v, dict):
                forms.append(v.get("name", ""))
            else:
                v = str(v)
                forms += [v, long_date(v) or "", short_date(v) or ""]
                if parse_time(v):
                    forms.append(clock(v))
        if any(form and form.lower() in lowered for form in forms):
            used.append(key)
    return used


def _revise(prompt: str) -> dict[str, Any]:
    facts = json_block(prompt, "facts") or {}
    post = json_block(prompt, "post") or {}
    code = (json_block(prompt, "instruction") or {}).get("code")
    text = str(post.get("text", ""))

    if code == "make_shorter":
        text = _shorter(text)
    elif code == "make_longer":
        extra = facts.get("audience")
        addition = f"Who it is for: {extra}." if extra and extra not in text else "See you there!"
        text = text.rstrip() + "\n\n" + addition
    elif code == "warmer":
        text = "Hi friends! " + text if not text.startswith("Hi friends! ") else text + " 😊"
    elif code == "more_formal":
        text = text.removeprefix("Hi friends! ").removeprefix("Hi! ").replace("!", ".")
        text = "We are pleased to share this update.\n\n" + text
    return {"text": text, "facts_used": _facts_in(text, facts)}


def _shorter(text: str) -> str:
    lines = text.split("\n")
    without_tags = [line for line in lines if not re.fullmatch(r"(?:#\w+\s*)+", line.strip())]
    if len("\n".join(without_tags).strip()) < len(text.strip()):
        return re.sub(r"\n{3,}", "\n\n", "\n".join(without_tags)).strip()
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) > 1:
        return "\n\n".join(paragraphs[:-1])
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:-1]) if len(sentences) > 1 else text


def _redraft(prompt: str) -> dict[str, Any]:
    facts = json_block(prompt, "facts") or {}
    post = json_block(prompt, "post") or {}
    change = json_block(prompt, "change") or {}
    text = str(post.get("text", ""))
    old, new = change.get("old"), change.get("new")

    if isinstance(old, list) and isinstance(new, list):
        for before, after in zip(old, new, strict=False):
            a = before.get("name") if isinstance(before, dict) else str(before)
            b = after.get("name") if isinstance(after, dict) else str(after)
            if a and b:
                text = text.replace(a, b)
    elif isinstance(old, str) and isinstance(new, str) and old:
        pairs = [(long_date(old), long_date(new)), (short_date(old), short_date(new))]
        if parse_time(old) and parse_time(new):
            pairs.append((clock(old), clock(new)))
        pairs.append((old, new))
        for a, b in pairs:
            if a and b is not None and a in text:
                text = text.replace(a, b)
    return {"text": text, "facts_used": _facts_in(text, facts)}
