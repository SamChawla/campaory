"""POST /brief/extract (LLD 5.1). The model proposes facts; the human confirms them."""

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, get_args
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, Response
from pydantic import ValidationError

from app.api.deps import Model
from app.api.models import CandidateFact, ExtractRequest, ExtractResponse, UrlSource
from app.api.review import label_provider, meta_for, no_model_meta
from app.core.errors import AppError
from app.domain.facts import (
    CRITICAL_KEYS,
    long_date,
    normalize_text,
    parse_date,
    parse_time,
    valid_timezone,
)
from app.domain.schemas import FactKey, Person, Source
from app.fetch.extract_text import extract_text
from app.llm.base import call_validated
from app.llm.mock import extract_facts
from app.llm.prompts import extract_prompt
from app.llm.schemas import ExtractedFact, ExtractOutput

router = APIRouter()

MIN_CHARS = 40
MAX_CHARS = 20_000
JS_HINT_CHARS = 600
SAMPLE_FILE = "sample_event.txt"
FACT_KEYS: tuple[str, ...] = get_args(FactKey)
PEOPLE = frozenset({"speakers", "judges", "mentors", "partners"})
DATES = frozenset({"start_date", "end_date", "registration_deadline"})
TIMES = frozenset({"start_time", "end_time"})
MODES = {"in person": "offline", "in-person": "offline", "virtual": "online"}


@router.post("/brief/extract", response_model=ExtractResponse)
async def extract(
    body: ExtractRequest, request: Request, response: Response, model: Model
) -> ExtractResponse:
    source = body.source
    warnings: list[str] = []

    if source.kind == "sample":
        sample = Path(request.app.state.settings.samples_dir) / SAMPLE_FILE
        text = sample.read_text(encoding="utf-8")
        facts = _candidates(
            [ExtractedFact.model_validate(f) for f in extract_facts(text)], text, "sample", warnings
        )
        return ExtractResponse(
            facts=facts,
            source=Source(kind="sample", text_hash=_hash(text)),
            warnings=warnings,
            meta=no_model_meta(),
        )

    if isinstance(source, UrlSource):
        text, fetched_at, ref = await _from_url(request, source.url, warnings)
        out_source = Source(
            kind="url", url=source.url, fetched_at=fetched_at, text_hash=_hash(text)
        )
    else:
        text, ref = source.text.strip(), "paste"
        if len(text) < MIN_CHARS:
            raise AppError(422, "text_too_short", "Paste at least a few lines about the event.")
        out_source = Source(kind="text", text_hash=_hash(text))

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        warnings.append(
            "The text was longer than 20,000 characters; only the first 20,000 were read."
        )

    result = await call_validated(model.provider(), extract_prompt(text), ExtractOutput)
    meta = meta_for([result])
    label_provider(response, meta)
    return ExtractResponse(
        facts=_candidates(result.data.facts, text, ref, warnings),
        source=out_source,
        warnings=warnings,
        meta=meta,
    )


async def _from_url(request: Request, url: str, warnings: list[str]) -> tuple[str, datetime, str]:
    page = await request.app.state.fetch_page(url)
    fetched_at = datetime.now(UTC).replace(microsecond=0)
    if page.content_type == "text/plain":
        text, scripts = page.text.strip(), 0
    else:
        extracted = extract_text(page.text)
        text, scripts = extracted.text, extracted.script_count
    if len(text) < MIN_CHARS:
        raise AppError(
            422,
            "text_too_short",
            "That page has almost no readable text. It may need JavaScript; "
            "paste the text instead.",
        )
    if scripts and len(text) < JS_HINT_CHARS:
        warnings.append("Page looks JavaScript-rendered; paste the text if facts are missing.")
    return text, fetched_at, url


def _hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _candidates(
    raw: list[ExtractedFact], text: str, ref: str, warnings: list[str]
) -> list[CandidateFact]:
    """Known keys only, first value per key, snippet must be in the source, criticals listed."""
    source = normalize_text(text)
    found: dict[str, CandidateFact] = {}
    unsupported: list[str] = []
    for item in raw:
        if item.key not in FACT_KEYS or item.key in found:
            continue
        value = _coerce(item.key, item.value)
        if value is None:
            continue
        snippet = item.source_snippet.strip()
        critical = item.key in CRITICAL_KEYS
        if not snippet or normalize_text(snippet) not in source:
            unsupported.append(item.key)
            found[item.key] = CandidateFact(
                key=item.key, value="", status="missing", critical=critical,
                source_snippet=None, source_ref=None,
            )  # fmt: skip
            continue
        found[item.key] = CandidateFact(
            key=item.key, value=value, status="needs_review", critical=critical,
            source_snippet=snippet[:2000], source_ref=ref,
        )  # fmt: skip
    if unsupported:
        warnings.append(
            "Left out details we could not find in the text: "
            + ", ".join(unsupported)
            + ". Add them by hand if they are right."
        )
    for key in CRITICAL_KEYS - found.keys():
        found[key] = CandidateFact(
            key=key, value="", status="missing", critical=True, source_snippet=None, source_ref=None
        )
    _warn_if_past(found, warnings)
    return [found[k] for k in FACT_KEYS if k in found]


def _warn_if_past(found: dict[str, CandidateFact], warnings: list[str]) -> None:
    """Old event pages are common; say so before the organizer plans posts for them."""
    days = []
    for key in ("end_date", "start_date"):
        fact = found.get(key)
        if fact and fact.status == "needs_review":
            try:
                days.append(date.fromisoformat(str(fact.value)))
            except ValueError:
                continue
    if not days:
        return
    tz_fact = found.get("timezone")
    tz_name = str(tz_fact.value) if tz_fact and tz_fact.value else "UTC"
    today = datetime.now(ZoneInfo(tz_name if valid_timezone(tz_name) else "UTC")).date()
    last = max(days)
    if last < today:
        warnings.append(
            f"This event has already passed ({long_date(last.isoformat())}). "
            "Check the dates, or plan follow-up posts only."
        )


def _coerce(key: str, value: Any) -> Any:
    """Turn model output into a valid fact value, or None when it is unusable."""
    if key in PEOPLE:
        return _people(value) or None
    if key in ("hashtags", "handles"):
        items = value if isinstance(value, list) else str(value).replace(",", " ").split()
        prefix = "#" if key == "hashtags" else "@"
        tags = [str(t).strip() for t in items if isinstance(t, str | int) and str(t).strip()]
        return [t if t.startswith(prefix) else prefix + t for t in tags][:50] or None
    if isinstance(value, list):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()[:2000]
    if not text:
        return None
    if key in DATES:
        parsed = parse_date(text)
        if parsed and parsed.year:
            return f"{parsed.year:04d}-{parsed.month:02d}-{parsed.day:02d}"
    if key in TIMES:
        parsed_time = parse_time(text)
        if parsed_time:
            return "{:02d}:{:02d}".format(*parsed_time)
    if key == "event_mode":
        lowered = text.lower()
        return MODES.get(lowered, lowered)
    return text


def _people(value: Any) -> list[Person]:
    items = value if isinstance(value, list) else str(value).split(",")
    people = []
    for item in items[:50]:
        data = item if isinstance(item, dict) else {"name": str(item).strip()}
        fields = {k: data.get(k) for k in ("name", "role", "url", "handle") if data.get(k)}
        try:
            people.append(Person.model_validate(fields))
        except ValidationError:
            continue
    return people
