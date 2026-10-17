from typing import Any

from fastapi import APIRouter, Request, Response

from app.core.security import CurrentUser, OptionalUser, clear_session
from app.db import repo
from app.db.session import DbSession

router = APIRouter()


@router.get("/me")
def me(user: OptionalUser) -> dict[str, Any]:
    return {"user": user.public() if user else None}


@router.delete("/me", status_code=204)
def delete_me(user: CurrentUser, request: Request, response: Response, db: DbSession) -> None:
    repo.delete_user(db, user.id)
    clear_session(response, request.app.state.settings)
