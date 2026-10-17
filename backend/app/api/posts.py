"""POST /posts/generate, /posts/revise, /posts/validate (LLD 5.3 to 5.5)."""

import asyncio

from fastapi import APIRouter, Response

from app.api.deps import Model
from app.api.models import (
    CheckedPost,
    FailedItem,
    GenerateItem,
    GenerateRequest,
    GenerateResponse,
    ReviseRequest,
    RewriteResponse,
    ValidateRequest,
    ValidateResponse,
)
from app.api.plan import blocked
from app.api.review import confirmed_keys, label_provider, meta_for, review
from app.core.errors import AppError
from app.domain.facts import confirmed, generation_blockers
from app.domain.schemas import PLATFORM_ORDER, Fact, Platform
from app.llm.base import LLMProvider, LLMResult, call_validated
from app.llm.prompts import generate_prompt, revise_prompt
from app.llm.schemas import GenerateOutput, RewrittenPost

router = APIRouter()


def published_refusal() -> AppError:
    return AppError(409, "published_post", "This post is published and cannot change.")


@router.post("/posts/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest, response: Response, model: Model) -> GenerateResponse:
    facts = confirmed(body.facts)
    missing = generation_blockers(facts, body.language)
    if missing:
        raise blocked(missing)
    platforms = [p for p in PLATFORM_ORDER if p in body.platforms]
    provider = model.provider()

    outcomes = await asyncio.gather(
        *(_generate_item(provider, facts, item, platforms, body) for item in body.items),
        return_exceptions=True,
    )

    posts: list[CheckedPost] = []
    failed: list[FailedItem] = []
    results: list[LLMResult] = []
    errors: list[AppError] = []
    for item, outcome in zip(body.items, outcomes, strict=True):
        if isinstance(outcome, AppError):
            errors.append(outcome)
            failed.append(FailedItem(plan_item_id=item.id, error=outcome.code))
        elif isinstance(outcome, BaseException):
            raise outcome
        else:
            result, checked = outcome
            results.append(result)
            posts.extend(checked)
    if not results:
        raise errors[0]
    meta = meta_for(results)
    label_provider(response, meta)
    return GenerateResponse(posts=posts, failed=failed, meta=meta)


async def _generate_item(
    provider: LLMProvider,
    facts: list[Fact],
    item: GenerateItem,
    platforms: list[Platform],
    body: GenerateRequest,
) -> tuple[LLMResult, list[CheckedPost]]:
    prompt_item = {
        "title": item.title,
        "purpose": item.purpose,
        "stage": item.stage,
        "fact_keys": item.fact_keys,
    }
    prompt = generate_prompt(facts, prompt_item, platforms, tone=body.tone, language=body.language)

    def one_per_platform(output: GenerateOutput) -> None:
        got = [p.platform for p in output.posts]
        if sorted(got) != sorted(platforms):
            raise ValueError(f"posts must contain exactly one entry for each of {platforms}")

    result = await call_validated(provider, prompt, GenerateOutput, check=one_per_platform)
    checked = []
    for post in sorted(result.data.posts, key=lambda p: PLATFORM_ORDER.index(p.platform)):
        flags, placeholders, validation, status = review(
            post.platform, post.text, facts, item.scheduled_for
        )
        checked.append(
            CheckedPost(
                plan_item_id=item.id,
                platform=post.platform,
                text=post.text,
                facts_used=confirmed_keys(post.facts_used, facts),
                status=status,
                guard_flags=flags,
                placeholders=placeholders,
                validation=validation,
            )
        )
    return result, checked


@router.post("/posts/revise", response_model=RewriteResponse)
async def revise(body: ReviseRequest, response: Response, model: Model) -> RewriteResponse:
    if body.post.status == "published":
        raise published_refusal()
    facts = confirmed(body.facts)
    prompt = revise_prompt(
        facts, body.post.platform, body.post.text, body.instruction, body.custom_instruction
    )
    result = await call_validated(model.provider(), prompt, RewrittenPost)
    return _rewrite(result, body.post.platform, facts, body.post.scheduled_for, response)


def _rewrite(result, platform, facts, scheduled_for, response: Response) -> RewriteResponse:
    text = result.data.text
    flags, placeholders, validation, status = review(platform, text, facts, scheduled_for)
    meta = meta_for([result])
    label_provider(response, meta)
    return RewriteResponse(
        text=text,
        facts_used=confirmed_keys(result.data.facts_used, facts),
        guard_flags=flags,
        placeholders=placeholders,
        validation=validation,
        status=status,
        meta=meta,
    )


@router.post("/posts/validate", response_model=ValidateResponse)
def validate_post(body: ValidateRequest) -> ValidateResponse:
    flags, placeholders, validation, _ = review(
        body.platform, body.text, body.facts, body.scheduled_for
    )
    return ValidateResponse(validation=validation, guard_flags=flags, placeholders=placeholders)
