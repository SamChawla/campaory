"""GET /config: what the UI needs to label the model and explain limits. No secrets."""

from typing import Any

from fastapi import APIRouter, Request

from app.api.brief import MAX_CHARS
from app.api.models import MAX_ITEMS_PER_GENERATE
from app.core.middleware import MAX_BODY_BYTES

router = APIRouter()

MOCK_LABEL = "Demo model"


@router.get("/config")
def config(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    is_mock = settings.llm_provider == "mock"
    return {
        "provider": settings.llm_provider,
        "model": MOCK_LABEL if is_mock else f"{settings.euri_model} via Euri",
        "llm_is_mock": is_mock,
        "fallback_to_mock": settings.llm_fallback_to_mock and not is_mock,
        "limits": {
            "guest_per_hour": settings.rate_guest_per_hour,
            "guest_per_day": settings.rate_guest_per_day,
            "user_per_hour": settings.rate_user_per_hour,
            "max_items_per_generate": MAX_ITEMS_PER_GENERATE,
            "max_source_chars": MAX_CHARS,
            "max_body_bytes": MAX_BODY_BYTES,
        },
        "auth_providers": ["google"] if settings.google_oauth_client_id else [],
    }
