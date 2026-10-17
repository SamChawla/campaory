"""Saved campaigns (LLD 5.8). Signed-in users only; every query is scoped by user id (BR12)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import AppError
from app.core.security import CurrentUser
from app.db import repo
from app.db.session import DbSession
from app.domain.schemas import MAX_DOCUMENT_BYTES, CampaignDoc, DocumentTooLarge, parse_document

router = APIRouter(prefix="/campaigns")

# PUT wraps the document in {"expected_version": n, "doc": ...}; allow a little room for that.
MAX_REPLACE_BYTES = MAX_DOCUMENT_BYTES + 1024


class ReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=1)]
    doc: CampaignDoc


def _too_large() -> AppError:
    return AppError(413, "payload_too_large", "The campaign is larger than 512 KB.")


async def _read_capped(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise _too_large()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise _too_large()
    return bytes(body)


async def _create_body(request: Request) -> bytes:
    return await _read_capped(request, MAX_DOCUMENT_BYTES)


async def _replace_body(request: Request) -> bytes:
    return await _read_capped(request, MAX_REPLACE_BYTES)


def _invalid(exc: ValidationError) -> RequestValidationError:
    return RequestValidationError(exc.errors(include_url=False, include_input=False))


def _not_json() -> AppError:
    return AppError(422, "validation_error", "The body is not valid JSON.", details={"fields": []})


def _not_found() -> AppError:
    return AppError(404, "not_found", "No such campaign.")


def _campaign_id(raw: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError:
        raise _not_found() from None


@router.get("")
def list_campaigns(user: CurrentUser, db: DbSession) -> dict[str, Any]:
    return {
        "campaigns": [
            {
                "id": str(row.id),
                "name": row.name,
                "version": row.version,
                "updated_at": row.updated_at.isoformat().replace("+00:00", "Z"),
                "post_counts": row.post_counts,
            }
            for row in repo.list_campaigns(db, user.id)
        ]
    }


@router.post("", status_code=201)
def create_campaign(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    response: Response,
    raw: Annotated[bytes, Depends(_create_body)],
) -> dict[str, Any]:
    try:
        doc = parse_document(raw)
    except DocumentTooLarge:
        raise _too_large() from None
    except ValidationError as exc:
        raise _invalid(exc) from None
    except ValueError:  # JSONDecodeError or UnicodeDecodeError
        raise _not_json() from None
    limit = request.app.state.settings.free_plan_max_campaigns
    saved, created = repo.create_campaign(db, user.id, doc, max_campaigns=limit)
    if not created:
        response.status_code = 200
    return {"id": str(saved.id), "version": saved.version}


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, user: CurrentUser, db: DbSession) -> JSONResponse:
    doc = repo.get_campaign(db, user.id, _campaign_id(campaign_id))
    if doc is None:
        raise _not_found()
    return JSONResponse(doc.model_dump(mode="json", by_alias=True))


@router.put("/{campaign_id}")
def replace_campaign(
    campaign_id: str,
    user: CurrentUser,
    db: DbSession,
    raw: Annotated[bytes, Depends(_replace_body)],
) -> dict[str, int]:
    target = _campaign_id(campaign_id)
    try:
        body = ReplaceRequest.model_validate_json(raw)
    except ValidationError as exc:
        if any(err["type"] == "json_invalid" for err in exc.errors()):
            raise _not_json() from None
        raise _invalid(exc) from None
    if body.doc.id != target:
        raise AppError(
            422,
            "validation_error",
            "The document id does not match the URL.",
            details={"fields": [{"loc": ["body", "doc", "id"], "msg": "does not match the URL"}]},
        )
    saved = repo.replace_campaign(db, user.id, target, body.doc, body.expected_version)
    if saved is None:
        raise _not_found()
    return {"version": saved.version}


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: str, user: CurrentUser, db: DbSession) -> None:
    if not repo.delete_campaign(db, user.id, _campaign_id(campaign_id)):
        raise _not_found()
