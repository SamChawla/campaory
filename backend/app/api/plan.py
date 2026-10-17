"""POST /plan/propose (LLD 5.2). Dates come from domain/planning.py; no model call."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.api.models import PlanRequest, PlanResponse, ProposedItemOut
from app.core.errors import AppError
from app.domain.facts import confirmed_map, generation_blockers, valid_timezone
from app.domain.planning import PlanBlocked, propose_plan

router = APIRouter()


def blocked(missing: list[str]) -> AppError:
    return AppError(
        422, "blocked", "Confirm these facts first: " + ", ".join(missing) + ".",
        details={"missing": missing},
    )  # fmt: skip


def invalid_timezone() -> AppError:
    return AppError(
        422,
        "validation_error",
        "Some fields are not valid.",
        details={"fields": [{"loc": ["body", "timezone"], "msg": "Unknown time zone"}]},
    )


@router.post("/plan/propose", response_model=PlanResponse)
def propose(body: PlanRequest) -> PlanResponse:
    missing = generation_blockers(body.facts, body.language)
    if missing:
        raise blocked(missing)
    timezone = body.timezone or str(confirmed_map(body.facts)["timezone"].value)
    if not valid_timezone(timezone):
        raise invalid_timezone()
    today = body.today or datetime.now(ZoneInfo(timezone)).date()
    try:
        items = propose_plan(
            body.facts, body.platforms, today=today, timezone=timezone, language=body.language
        )
    except PlanBlocked as exc:
        raise blocked(exc.missing) from exc
    return PlanResponse(
        items=[
            ProposedItemOut(
                title=i.title,
                purpose=i.purpose,
                stage=i.stage,
                scheduled_for=i.scheduled_for,
                fact_keys=i.fact_keys,
                platforms=i.platforms,
            )
            for i in items
        ]
    )
