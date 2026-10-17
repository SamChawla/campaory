"""POST /impact/analyze and /impact/redraft (LLD 5.6, 5.7). Published posts never change."""

from datetime import date

from fastapi import APIRouter, Response

from app.api.deps import Model
from app.api.models import (
    AffectedOut,
    AnalyzeRequest,
    AnalyzeResponse,
    Changed,
    PlanChangeOut,
    ProtectedOut,
    RedraftRequest,
    RedraftResponse,
    SpanOut,
)
from app.api.posts import published_refusal
from app.api.review import confirmed_keys, label_provider, meta_for, review
from app.domain.facts import confirmed
from app.domain.impact import Change, analyze
from app.domain.schemas import Person
from app.domain.textdiff import changed_spans
from app.llm.base import call_validated
from app.llm.prompts import redraft_prompt
from app.llm.schemas import RewrittenPost

router = APIRouter()


def _change(changed: Changed) -> Change:
    return Change(changed.key, changed.old, changed.new)


def _plain(value):
    if isinstance(value, list):
        return [v.model_dump(exclude_none=True) if isinstance(v, Person) else v for v in value]
    return value


def _show(value) -> str:
    if isinstance(value, list):
        return ", ".join(v.name if isinstance(v, Person) else str(v) for v in value) or "nothing"
    return value or "nothing"


@router.post("/impact/analyze", response_model=AnalyzeResponse)
def impact_analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    result = analyze(
        _change(body.changed),
        body.facts,
        body.posts,
        body.plan,
        today=body.today or date.today(),
        language=body.language,
    )
    return AnalyzeResponse(
        affected=[
            AffectedOut(post_id=a.post_id, reason=a.reason, detail=a.detail)
            for a in result.affected
        ],
        protected=[
            ProtectedOut(post_id=p.post_id, status=p.status, note=p.note) for p in result.protected
        ],
        plan_changes=[
            PlanChangeOut(plan_item_id=c.plan_item_id, field=c.field, old=c.old, new=c.new)
            for c in result.plan_changes
        ],
    )


@router.post("/impact/redraft", response_model=RedraftResponse)
async def impact_redraft(body: RedraftRequest, response: Response, model: Model) -> RedraftResponse:
    if body.post.status == "published":
        raise published_refusal()
    facts = confirmed(body.facts)
    change = {
        "key": body.changed.key,
        "old": _plain(body.changed.old),
        "new": _plain(body.changed.new),
    }
    prompt = redraft_prompt(facts, body.post.platform, body.post.text, change)
    result = await call_validated(model.provider(), prompt, RewrittenPost)

    text = result.data.text
    flags, placeholders, validation, status = review(
        body.post.platform, text, facts, body.scheduled_for
    )
    meta = meta_for([result])
    label_provider(response, meta)
    return RedraftResponse(
        proposed_text=text,
        changed_spans=[
            SpanOut(from_=a.strip(), to=b.strip()) for a, b in changed_spans(body.post.text, text)
        ],
        reason=f"{body.changed.key} changed from {_show(body.changed.old)} to "
        f"{_show(body.changed.new)}",
        facts_used=confirmed_keys(result.data.facts_used, facts),
        guard_flags=flags,
        placeholders=placeholders,
        validation=validation,
        status=status,
        meta=meta,
    )
