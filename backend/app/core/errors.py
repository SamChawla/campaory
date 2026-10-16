import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("campaory")


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str = "",
        *,
        details: dict[str, Any] | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        self.retry_after_seconds = retry_after_seconds


def error_response(
    status: int,
    code: str,
    message: str = "",
    details: dict[str, Any] | None = None,
    retry_after_seconds: int | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, "details": details or {}}
    headers = {}
    if retry_after_seconds is not None:
        body["retry_after_seconds"] = retry_after_seconds
        headers["Retry-After"] = str(retry_after_seconds)
    return JSONResponse({"error": body}, status_code=status, headers=headers)


_HTTP_CODES = {401: "unauthorized", 404: "not_found", 405: "not_found", 413: "payload_too_large"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(
            exc.status, exc.code, exc.message, exc.details, exc.retry_after_seconds
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": [str(p) for p in err["loc"]], "msg": err["msg"]} for err in exc.errors()]
        return error_response(
            422, "validation_error", "Some fields are not valid.", {"fields": fields}
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "server_error")
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s", type(exc).__name__)
        return error_response(500, "server_error", "Something went wrong on our side.")
